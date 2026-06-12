"""Jenkins Plugin management commands."""

from __future__ import annotations

import click

from jcli.cli_helpers import get_client, get_formatter
from jcli.sdk.plugin import (
    check_plugin_updates,
    get_plugin,
    install_plugins,
    list_plugins,
    uninstall_plugin,
)


def _parse_plugin_spec(spec: str) -> tuple[str, str | None]:
    """Parse a plugin spec like 'git' or 'git@5.0.0'.

    Returns:
        (short_name, version_or_None)
    """
    if "@" in spec:
        name, _, version = spec.partition("@")
        return name, version
    return spec, None


# ------------------------------------------------------------------
# Plugin command group
# ------------------------------------------------------------------


@click.group("plugin", help="Manage Jenkins plugins.")
@click.pass_context
def plugin_group(ctx):
    """Plugin management commands."""


@plugin_group.command("list")
@click.pass_context
def list_cmd(ctx):
    """List installed Jenkins plugins."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    try:
        plugins = list_plugins(client)
    except Exception as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1)

    if not plugins:
        fmt.print_info("No plugins found.")
        return

    headers = ["Name", "Version", "Active", "Update"]
    rows = [
        [p.get("shortName", "?"), p.get("version", "?"),
         "Yes" if p.get("active") else "No",
         "Yes" if p.get("hasUpdate") else "No"]
        for p in plugins
    ]
    fmt.print_table(headers, rows, title="Installed Plugins")


@plugin_group.command("get")
@click.argument("name")
@click.pass_context
def get_cmd(ctx, name):
    """Show details for a single plugin."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    try:
        plugin = get_plugin(client, name)
    except Exception as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1)

    # Display all fields in a vertical key-value table
    headers = ["Field", "Value"]
    rows = [[str(k), str(v)] for k, v in plugin.items()] if plugin else []
    fmt.print_table(
        headers,
        rows,
        title=f"Plugin: {plugin.get('shortName', name)}" if plugin else f"Plugin {name}",
    )


@plugin_group.command("install")
@click.argument("plugin_spec")
@click.pass_context
def install_cmd(ctx, plugin_spec):
    """Install a Jenkins plugin.

    PLUGIN_SPEC can be just a plugin name (e.g. 'git') or
    name@version (e.g. 'git@5.0.0') to install a specific version.
    """
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    name, version = _parse_plugin_spec(plugin_spec)
    plugins_dict: dict[str, str | None] = {name: version}

    try:
        install_plugins(client, plugins_dict)
    except Exception as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1)

    msg = f"Plugin '{name}' installed successfully"
    if version:
        msg += f" (version {version})"
    fmt.print_success(msg)


@plugin_group.command("uninstall")
@click.argument("name")
@click.pass_context
def uninstall_cmd(ctx, name):
    """Uninstall a Jenkins plugin.

    The plugin is scheduled for removal; a server restart is typically
    required to complete the uninstall.
    """
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    try:
        uninstall_plugin(client, name)
    except Exception as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1)

    fmt.print_success(f"Plugin '{name}' scheduled for uninstall (restart may be required)")


@plugin_group.command("check-updates")
@click.pass_context
def check_updates_cmd(ctx):
    """Check for available plugin updates."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)
    try:
        result = check_plugin_updates(client)
        fmt.print_info("Plugin update check triggered. Run 'jcli plugin list' to see results.")
        if isinstance(result, dict) and result:
            fmt.print_json(result)
    except Exception as exc:
        fmt.print_error(str(exc))


@plugin_group.command("restart")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@click.pass_context
def restart_cmd(ctx, yes):
    """Restart Jenkins after plugin changes."""
    if not yes:
        click.confirm("Restart Jenkins server?", abort=True)
    client = get_client(ctx)
    fmt = get_formatter(ctx)
    try:
        from jcli.sdk.system import safe_restart
        safe_restart(client)
        fmt.print_success("Jenkins restart initiated.")
    except Exception as exc:
        fmt.print_error(str(exc))


def register(parent_group):
    """Register the plugin subgroup under the parent Click group."""
    parent_group.add_command(plugin_group)
