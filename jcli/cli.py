"""Jenkins CLI - Command line interface for managing Jenkins.

jcli 2.0 wrapper: the Click CLI is generated from the cliyard YAML specs
(``specs/``) and this module layers the global options on top:

* ``-f/--format`` — table / json / yaml / csv (default ``table``)
* ``-p/--profile`` — pick a profile from ``~/.jcli/config.yaml``
* ``-d/--debug`` — enable DEBUG logging on stderr
* ``-s/--server`` — handled by cliyard's runner pre-extraction
  (:func:`cliyard.runtime.runner.extract_server_override`); it is *not*
  redefined here to avoid conflicting with cliyard.

The global ``-f`` is injected into each subcommand callback only when the
subcommand did not explicitly set its own ``--format`` on the command line
(cliyard's ``_make_callback`` pops ``format`` from kwargs, so a plain default
would shadow the global override).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable

import click
from click.core import ParameterSource

from cliyard.runtime import create_cli
from cliyard.runtime.runner import extract_server_override

from jcli import __version__

logger = logging.getLogger("jcli")

#: Formats accepted by the global ``-f/--format`` option (superset of
#: cliyard's built-ins, adding ``yaml``).
GLOBAL_FORMATS = ("table", "json", "yaml", "csv")

#: Env var to override the cliyard spec directory (mainly for tests/dev).
SPEC_DIR_ENV = "JCLI_SPEC_DIR"


# ---------------------------------------------------------------------------
# Spec directory & base_url resolution
# ---------------------------------------------------------------------------


def _default_spec_dir() -> Path:
    """Locate the cliyard YAML spec directory (ships inside the package).

    Priority: ``$JCLI_SPEC_DIR`` env var > package-local ``jcli/specs/``.
    """
    env = os.environ.get(SPEC_DIR_ENV)
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / "specs"


def extract_profile_override(argv: list[str]) -> str | None:
    """Read a ``--profile``/``-p`` value from *argv* without removing it.

    The top-level ``-p/--profile`` Click option parses the flag normally; this
    only previews the value so the base_url can be resolved before the CLI tree
    is built.  ``--profile X``, ``--profile=X``, ``-p X`` and ``-p=X`` forms
    are supported.
    """
    profile: str | None = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--profile", "-p") and i + 1 < len(argv) and not argv[i + 1].startswith("-"):
            profile = argv[i + 1]
            i += 2
            continue
        if arg.startswith("--profile="):
            profile = arg.split("=", 1)[1]
            i += 1
            continue
        if arg.startswith("-p=") and len(arg) > 3:
            profile = arg[3:]
            i += 1
            continue
        i += 1
    return profile


def _read_profile_url(profile_name: str | None) -> str | None:
    """Read a profile URL from ``~/.jcli/config.yaml`` (read-only, no creation)."""
    import yaml as _yaml

    from jcli.sdk.config import DEFAULT_CONFIG_FILE, ENV_PROFILE

    try:
        if not DEFAULT_CONFIG_FILE.exists():
            return None
        cfg = _yaml.safe_load(DEFAULT_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(cfg, dict):
        return None
    name = profile_name or os.environ.get(ENV_PROFILE) or cfg.get("active_profile") or "default"
    profiles = cfg.get("profiles")
    if not isinstance(profiles, dict):
        return None
    profile = profiles.get(name)
    if not isinstance(profile, dict):
        return None
    url = profile.get("url")
    return url if isinstance(url, str) and url.strip() else None


def resolve_base_url(server_override: str | None, profile_name: str | None) -> str | None:
    """Resolve the base_url handed to ``create_cli(base_url_override=...)``.

    Precedence: ``-s/--server`` > ``JCLI_URL`` env > profile ``url`` from
    ``~/.jcli/config.yaml``.  ``None`` lets cliyard fall back to the spec's
    ``server.base_url``.
    """
    if server_override:
        return server_override
    env_url = os.environ.get("JCLI_URL")
    if env_url:
        return env_url
    return _read_profile_url(profile_name)


# ---------------------------------------------------------------------------
# Global options & format injection
# ---------------------------------------------------------------------------


def add_global_options(cli: click.Group) -> None:
    """Attach global options (``-f/--format``, ``-p/--profile``, ``-d/--debug``).

    Values are stored in ``ctx.obj`` so wrapped subcommand callbacks can read
    them.  ``-s/--server`` is intentionally *not* added here — cliyard's
    ``create_cli`` already registers it on the top-level group (with a root
    callback that stores the override into ``ctx.obj["server"]``); that
    behavior is preserved by the combined callback below.

    Note: ``Group.callback`` is a plain attribute in Click 8.4 (the
    ``@cli.callback`` decorator form is gone), so the callback and its options
    are assigned explicitly.
    """
    cli.params.extend(
        [
            click.Option(
                ["-f", "--format", "output_format"],
                default="table",
                type=click.Choice(GLOBAL_FORMATS),
                help="Output format.",
                show_default=True,
            ),
            click.Option(["-p", "--profile"], default=None, help="Configuration profile name."),
            click.Option(["-d", "--debug"], is_flag=True, default=False, help="Enable debug output."),
        ]
    )

    @click.pass_context
    def _global_options(
        ctx: click.Context,
        output_format: str,
        profile: str | None,
        debug: bool,
        **extra: Any,
    ) -> None:
        ctx.ensure_object(dict)

        # Preserve cliyard's root-callback behavior: the native --server/-s
        # option (registered by create_cli) is stored for subcommands.
        server = extra.get("server")
        if server:
            ctx.obj["server"] = server

        ctx.obj["format"] = output_format
        ctx.obj["profile"] = profile
        ctx.obj["debug"] = debug

        if debug:
            logging.basicConfig(
                level=logging.DEBUG,
                format="%(asctime)s %(name)s %(levelname)s %(message)s",
                stream=sys.stderr,
                force=True,
            )
            logger.debug("Debug logging enabled")
        else:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, force=True)

    cli.callback = _global_options


def _make_format_injector(callback: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a subcommand callback so the global ``-f/--format`` is applied.

    cliyard's ``_make_callback`` pops ``format`` from kwargs and falls back to
    the method's own default — a default therefore shadows a global override.
    We inspect the parameter source and only inject the global format when the
    subcommand did not explicitly pass ``--format`` on the command line.

    cliyard's callbacks also swallow every exception and print the message to
    the console without re-raising, so connection failures / API errors would
    otherwise exit 0.  The wrapped callback captures stdout, recognises the
    ``Error:``/``错误:`` markers and re-emits them on stderr with a non-zero
    exit code.

    Commands carrying a ``--follow`` flag (live log tailing) bypass the
    stdout capture so the plugin can stream output in real time.

    Note: ``ctx.exit(1)`` (not ``return 1``) is required — Click >= 8.4
    ignores a plain integer return value from the top-level callback and
    always exits with ``ctx.exit_code`` (default 0).
    """
    import io

    def wrapped(**kwargs: Any) -> Any:
        ctx = click.get_current_context()
        root = ctx.find_root()
        global_format = (root.obj or {}).get("format")
        if global_format:
            try:
                source = ctx.get_parameter_source("format")
            except Exception:
                source = ParameterSource.DEFAULT
            if source in (None, ParameterSource.DEFAULT, ParameterSource.DEFAULT_MAP):
                kwargs["format"] = global_format

        if kwargs.get("follow"):
            return callback(**kwargs)

        buffer = io.StringIO()
        real_stdout = sys.stdout
        sys.stdout = buffer
        try:
            result = callback(**kwargs)
        finally:
            sys.stdout = real_stdout

        output = buffer.getvalue()
        if output.startswith(("错误:", "Error:")):
            click.echo(output, err=True, nl=False)
            ctx.exit(1)
        if output:
            click.echo(output, nl=False)
        return result

    wrapped.__name__ = getattr(callback, "__name__", "callback")
    wrapped.__doc__ = getattr(callback, "__doc__", None)
    return wrapped


def wrap_subcommand_callbacks(command: click.Command) -> None:
    """Recursively wrap leaf-command callbacks to inherit the global format."""
    if isinstance(command, click.Group):
        for sub in command.commands.values():
            wrap_subcommand_callbacks(sub)
        return
    if any(getattr(p, "name", None) == "format" for p in command.params):
        command.callback = _make_format_injector(command.callback)


def add_completion_command(cli: click.Group) -> None:
    """Attach the ``completion show`` command (kept from jcli v1)."""

    @click.group()
    def completion() -> None:
        """Shell completion support for jcli."""

    @completion.command()
    @click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
    def show(shell: str) -> None:
        """Output shell completion script for the specified shell."""
        from click.shell_completion import BashComplete, FishComplete, ZshComplete

        shell_cls = {"bash": BashComplete, "zsh": ZshComplete, "fish": FishComplete}
        complete = shell_cls[shell](cli, {}, "jcli", "_JCLI_COMPLETE")
        click.echo(complete.source(), nl=False)

    cli.add_command(completion)


def set_group_help(cli: click.Group) -> None:
    """Propagate each command's ``short_help`` to its ``help`` text.

    cliyard only sets ``short_help`` (from the YAML ``description``), so
    ``jcli job --help`` / ``jcli plugin list --help`` would otherwise render
    without the description line.  jcli v1 printed it, so keep that
    behaviour: the top-level help lists commands via ``short_help``
    (unchanged), while per-command ``--help`` pages show the description.
    """
    stack = list(cli.commands.values())
    while stack:
        command = stack.pop()
        if isinstance(command, click.Group):
            stack.extend(command.commands.values())
        if command.short_help and not command.help:
            command.help = command.short_help


# ---------------------------------------------------------------------------
# CLI construction & entry point
# ---------------------------------------------------------------------------

# Commands belonging to jcli.  cliyard auto-registers ``auth`` (built-in)
# and any global plugins found in ~/.cliyard/plugins/ (other projects), so
# only whitelisted top-level commands are kept on the jcli command surface.
_ALLOWED_TOP_LEVEL_COMMANDS = {
    "job", "build", "node", "plugin", "credential", "pipeline", "view",
    "system", "skills", "completion", "auth",
}


def _prune_non_jcli_commands(cli: click.Group) -> None:
    """Drop top-level commands that are not part of jcli."""
    for name in list(cli.commands.keys()):
        if name not in _ALLOWED_TOP_LEVEL_COMMANDS:
            cli.commands.pop(name)


def _mask_token(token: str) -> str:
    """Mask an API token for display (``abcd****wxyz``)."""
    if len(token) > 8:
        return f"{token[:4]}****{token[-4:]}"
    return "****" if token else "-"


def _add_jcli_auth_commands(cli: click.Group) -> None:
    """Register the jcli-native ``auth`` command group.

    Replaces cliyard's built-in ``auth``, which writes ``~/.cliyard/
    credentials.yaml`` and is unrelated to jcli's actual authentication
    source.  This group reads/writes ``~/.jcli/config.yaml`` through the
    same :class:`jcli.sdk.config.Config` class as ``jcli config``, so the
    two command families share a single configuration source.
    """
    import copy

    from jcli.sdk.config import (
        DEFAULT_CONFIG_TEMPLATE,
        DEFAULT_PROFILE_NAME,
        ProfileNotFoundError,
        Config,
    )

    @click.group()
    def auth() -> None:
        """Manage Jenkins authentication profiles."""

    def _get_config() -> Config:
        return Config().load()

    @auth.command("add")
    @click.option("-n", "--name", default=DEFAULT_PROFILE_NAME, help="Profile name.")
    @click.option("-u", "--username", required=True, help="Jenkins username.")
    @click.option(
        "-p",
        "--password",
        "api_token",
        required=True,
        help="Jenkins API token (Jenkins Basic Auth = username:token).",
    )
    @click.option("-e", "--endpoint", "url", required=True, help="Jenkins server URL.")
    @click.option("--default", "set_default", is_flag=True, help="Set as the active profile.")
    def auth_add(name: str, username: str, api_token: str, url: str, set_default: bool) -> None:
        """Add (or update) an authentication profile in ~/.jcli/config.yaml."""
        cfg = _get_config()
        has_custom = any(p != DEFAULT_PROFILE_NAME for p in cfg.list_profiles())
        cfg.add_profile(name=name, url=url, username=username, api_token=api_token)
        if set_default or not has_custom:
            cfg.set_active_profile(name)
        click.echo(f"Profile '{name}' added ({'active' if cfg.get_active_profile_name() == name else 'inactive'}).")

    @auth.command("status")
    @click.pass_context
    def auth_status(ctx: click.Context) -> None:
        """List configured authentication profiles (tokens masked)."""
        from jcli.sdk.output.formatter import get_formatter

        fmt = get_formatter(ctx.find_root())
        cfg = _get_config()
        profiles = cfg.list_profiles()
        active_name = cfg.get_active_profile_name()

        if not profiles:
            fmt.print_info("No profiles configured. Run 'jcli auth add' to create one.")
            return

        headers = ["Name", "URL", "Username", "Token", "Active"]
        rows = []
        for name, data in profiles.items():
            rows.append(
                [
                    name,
                    data.get("url", ""),
                    data.get("username", ""),
                    _mask_token(data.get("api_token", "")),
                    "✓" if name == active_name else "",
                ]
            )
        fmt.print_table(headers, rows, title="Profiles")

    def _auth_use(profile: str) -> None:
        cfg = _get_config()
        try:
            cfg.set_active_profile(profile)
        except ProfileNotFoundError:
            click.echo(f"Error: Profile '{profile}' not found", err=True)
            available = ", ".join(cfg.list_profiles())
            if available:
                click.echo(f"Available profiles: {available}", err=True)
            raise click.exceptions.Exit(1)
        click.echo(f"Active profile set to '{profile}'")

    @auth.command("use")
    @click.argument("profile")
    def auth_use(profile: str) -> None:
        """Switch the active authentication profile."""
        _auth_use(profile)

    @auth.command("switch", hidden=True)
    @click.argument("profile")
    def auth_switch(profile: str) -> None:
        """Alias of ``auth use``."""
        _auth_use(profile)

    @auth.command("rm")
    @click.argument("name", required=False)
    @click.option("--all", "clear_all", is_flag=True, help="Remove all profiles and reset to the default template.")
    def auth_rm(name: str | None, clear_all: bool) -> None:
        """Remove an authentication profile (or all with --all)."""
        cfg = _get_config()
        if name:
            try:
                cfg.remove_profile(name)
            except ProfileNotFoundError:
                click.echo(f"Error: Profile '{name}' not found", err=True)
                raise click.exceptions.Exit(1)
            click.echo(f"Profile '{name}' removed")
        elif clear_all:
            cfg._data = copy.deepcopy(DEFAULT_CONFIG_TEMPLATE)
            cfg.save()
            click.echo("All profiles removed, config reset to the default template.")
        else:
            active = cfg.get_active_profile_name()
            click.echo(f"Active profile: {active} (use 'jcli auth rm NAME' or 'jcli auth rm --all')")

    @auth.command("set")
    @click.argument("name")
    @click.argument("field", type=click.Choice(["url", "username", "api_token", "description"]))
    @click.argument("value")
    def auth_set(name: str, field: str, value: str) -> None:
        """Set a configuration field (url/username/api_token/description) for a profile."""
        cfg = _get_config()
        try:
            data = cfg.get_profile(name)
        except ProfileNotFoundError:
            click.echo(f"Error: Profile '{name}' not found", err=True)
            raise click.exceptions.Exit(1)
        data[field] = value
        cfg.add_profile(
            name=name,
            url=data.get("url", ""),
            username=data.get("username", ""),
            api_token=data.get("api_token", ""),
            description=data.get("description", ""),
        )
        click.echo(f"Updated profile '{name}': {field} = {value}")

    @auth.command("show")
    @click.argument("name", required=False)
    def auth_show(name: str | None) -> None:
        """Show profile details (default: active profile, token masked)."""
        cfg = _get_config()
        if name is None:
            name = cfg.get_active_profile_name()
        try:
            data = cfg.get_profile(name)
        except ProfileNotFoundError:
            click.echo(f"Error: Profile '{name}' not found", err=True)
            raise click.exceptions.Exit(1)
        active_name = cfg.get_active_profile_name()
        is_active = " (active)" if name == active_name else ""
        click.echo(f"Profile: {name}{is_active}")
        fields = [
            ("url", "URL"),
            ("username", "Username"),
            ("api_token", "API Token"),
            ("description", "Description"),
        ]
        for key, label in fields:
            value = data.get(key, "")
            display = _mask_token(value) if key == "api_token" else value
            click.echo(f"  {label}: {display}")

    cli.add_command(auth)


def _add_tail_short_options(cli: click.Group) -> None:
    """Give ``build log`` tail-style short flags (``-f``/``-n``).

    cliyard generates long-only options (``--follow``/``--lines``); add the
    conventional ``tail`` short aliases on the ``build log`` command.
    """
    build = cli.commands.get("build")
    if not isinstance(build, click.Group):
        return
    log = build.commands.get("log")
    if not log:
        return
    for p in log.params:
        if isinstance(p, click.Option):
            if p.name == "follow" and "-f" not in p.opts:
                p.opts = ("-f", "--follow")
            elif p.name == "lines" and "-n" not in p.opts:
                p.opts = ("-n", "--lines")


def _build_cli(spec_dir: Path, server: str | None, profile: str | None) -> click.Group:
    """Create the cliyard CLI and apply the jcli wrapper layer."""
    base_url = resolve_base_url(server, profile)
    cli = create_cli(str(spec_dir), version=__version__, base_url_override=base_url)
    cli.commands.pop("auth", None)
    _add_jcli_auth_commands(cli)
    add_global_options(cli)
    add_completion_command(cli)
    wrap_subcommand_callbacks(cli)
    set_group_help(cli)
    _prune_non_jcli_commands(cli)
    _add_tail_short_options(cli)
    return cli


def create_jcli_cli(argv: list[str] | None = None) -> click.Group:
    """Build the jcli Click CLI from the YAML specs (wrapper included).

    With *argv* left ``None`` the real ``sys.argv`` is used and
    ``-s/--server`` is stripped from it (cliyard's runner pre-extraction).
    Tests pass an explicit argv to avoid touching ``sys.argv``.
    """
    if argv is None:
        argv = sys.argv[1:]
        cleaned, server = extract_server_override(argv)
        if cleaned != argv:
            sys.argv = [sys.argv[0]] + cleaned
        profile = extract_profile_override(cleaned)
    else:
        cleaned, server = extract_server_override(list(argv))
        profile = extract_profile_override(argv)
    return _build_cli(_default_spec_dir(), server, profile)


def main() -> None:
    """CLI entry point."""
    try:
        cli = create_jcli_cli()
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    try:
        code = cli(standalone_mode=False)
        sys.exit(code if code is not None else 0)
    except SystemExit as e:
        sys.exit(int(e.code) if e.code is not None else 0)
    except click.exceptions.ClickException as exc:
        click.echo(exc.format_message(), err=True)
        sys.exit(exc.exit_code)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


class _LazyCLI:
    """Lazy proxy so ``from jcli.cli import cli`` keeps working (tests/scripts).

    Each access rebuilds the CLI from the current specs, so no stale state is
    cached.  The real entry point is :func:`main` (console script target).
    """

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return create_jcli_cli(sys.argv[1:])(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(create_jcli_cli(sys.argv[1:]), name)


cli = _LazyCLI()


if __name__ == "__main__":
    main()
