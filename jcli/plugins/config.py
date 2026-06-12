"""Configuration management CLI commands for jcli."""

import click

from jcli.sdk.config import Config, ProfileNotFoundError
from jcli.sdk.output.formatter import OutputFormatter


def _get_config(ctx: click.Context) -> Config:
    """Get or create Config from Click context."""
    if "config" not in ctx.obj:
        ctx.obj["config"] = Config().load()
    return ctx.obj["config"]


def _get_formatter(ctx: click.Context) -> OutputFormatter:
    """Get or create OutputFormatter from Click context."""
    if "formatter" not in ctx.obj:
        fmt = ctx.obj.get("format", "table")
        ctx.obj["formatter"] = OutputFormatter(fmt)
    return ctx.obj["formatter"]


@click.group()
def config_group():
    """Manage jcli configuration."""
    pass


@config_group.command("init")
@click.option("--force", is_flag=True, help="Overwrite existing config file")
@click.pass_context
def config_init(ctx: click.Context, force: bool):
    """Initialize configuration file with default template."""
    cfg = _get_config(ctx)
    fmt = _get_formatter(ctx)

    if cfg.config_path.exists() and not force:
        fmt.print_error(f"Config file already exists: {cfg.config_path}")
        fmt.print_info("Use --force to overwrite")
        return

    # Create fresh config with template
    cfg = Config()
    cfg.load()
    cfg.save()

    fmt.print_success(f"Config file created: {cfg.config_path}")
    fmt.print_info("Edit it with your Jenkins server details:")
    fmt.print_info(f"  url: https://jenkins.example.com")
    fmt.print_info(f"  username: admin")
    fmt.print_info(f"  api_token: your-api-token-here")


@config_group.command("show")
@click.option("--profile", "-p", help="Show specific profile (default: active)")
@click.pass_context
def config_show(ctx: click.Context, profile: str | None):
    """Show configuration details."""
    cfg = _get_config(ctx)
    fmt = _get_formatter(ctx)

    if profile:
        try:
            data = cfg.get_profile(profile)
        except ProfileNotFoundError:
            fmt.print_error(f"Profile '{profile}' not found")
            return
        active_name = cfg.get_active_profile_name()
        is_active = " (active)" if profile == active_name else ""
        fmt.print_info(f"Profile: {profile}{is_active}")
        _show_profile(fmt, data)
    else:
        active_name = cfg.get_active_profile_name()
        fmt.print_info(f"Config file: {cfg.config_path}")
        fmt.print_info(f"Active profile: {active_name}")
        fmt.print_info("")
        try:
            data = cfg.get_active_profile()
            _show_profile(fmt, data)
        except ProfileNotFoundError:
            fmt.print_error(f"Active profile '{active_name}' not found")


def _show_profile(fmt: OutputFormatter, data: dict):
    """Display profile fields."""
    fields = [
        ("url", "URL"),
        ("username", "Username"),
        ("api_token", "API Token"),
        ("description", "Description"),
    ]
    for key, label in fields:
        value = data.get(key, "")
        # Mask token for display
        if key == "api_token" and value and len(value) > 8:
            display = value[:4] + "****" + value[-4:]
        else:
            display = value
        fmt.print_info(f"  {label}: {display}")


@config_group.command("list")
@click.pass_context
def config_list(ctx: click.Context):
    """List all configured profiles."""
    cfg = _get_config(ctx)
    fmt = _get_formatter(ctx)

    profiles = cfg.list_profiles()
    active_name = cfg.get_active_profile_name()

    if not profiles:
        fmt.print_info("No profiles configured. Run 'jcli config init' to create one.")
        return

    headers = ["Name", "URL", "Username", "Active"]
    rows = []
    for name, data in profiles.items():
        active_mark = "✓" if name == active_name else ""
        rows.append([
            name,
            data.get("url", ""),
            data.get("username", ""),
            active_mark,
        ])

    fmt.print_table(headers, rows, title="Profiles")


@config_group.command("set")
@click.argument("profile")
@click.argument("field", type=click.Choice(["url", "username", "api_token", "description"]))
@click.argument("value")
@click.pass_context
def config_set(ctx: click.Context, profile: str, field: str, value: str):
    """Set a configuration field for a profile.

    Examples:
        jcli config set dev url https://jenkins-dev.example.com
        jcli config set dev username admin
        jcli config set dev api_token abc123
        jcli config set dev description "Development Jenkins"
    """
    cfg = _get_config(ctx)
    fmt = _get_formatter(ctx)

    try:
        data = cfg.get_profile(profile)
    except ProfileNotFoundError:
        fmt.print_error(f"Profile '{profile}' not found")
        fmt.print_info(f"Create it first with: jcli config add {profile}")
        return

    # Update the field
    data[field] = value
    cfg.add_profile(
        name=profile,
        url=data.get("url", ""),
        username=data.get("username", ""),
        api_token=data.get("api_token", ""),
        description=data.get("description", ""),
    )

    fmt.print_success(f"Updated profile '{profile}': {field} = {value}")


@config_group.command("add")
@click.argument("profile")
@click.option("--url", "-u", default="", help="Jenkins server URL")
@click.option("--username", default="", help="Jenkins username")
@click.option("--api-token", default="", help="Jenkins API token")
@click.option("--description", "-d", default="", help="Profile description")
@click.pass_context
def config_add(
    ctx: click.Context,
    profile: str,
    url: str,
    username: str,
    api_token: str,
    description: str,
):
    """Add a new configuration profile.

    Examples:
        jcli config add dev --url https://jenkins-dev.example.com --username admin
        jcli config add prod -u https://jenkins-prod.example.com -d "Production"
    """
    cfg = _get_config(ctx)
    fmt = _get_formatter(ctx)

    # Check if profile already exists
    profiles = cfg.list_profiles()
    if profile in profiles:
        fmt.print_error(f"Profile '{profile}' already exists")
        fmt.print_info(f"Use 'jcli config set {profile} <field> <value>' to update")
        return

    cfg.add_profile(
        name=profile,
        url=url or "https://jenkins.example.com",
        username=username or "admin",
        api_token=api_token or "",
        description=description or f"{profile} Jenkins instance",
    )

    fmt.print_success(f"Profile '{profile}' added")
    fmt.print_info("Configure it with:")
    fmt.print_info(f"  jcli config set {profile} url https://your-jenkins.com")
    fmt.print_info(f"  jcli config set {profile} api_token your-token")


@config_group.command("delete")
@click.argument("profile")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.pass_context
def config_delete(ctx: click.Context, profile: str, yes: bool):
    """Delete a configuration profile.

    Examples:
        jcli config delete dev
        jcli config delete old-server --yes
    """
    cfg = _get_config(ctx)
    fmt = _get_formatter(ctx)

    profiles = cfg.list_profiles()
    if profile not in profiles:
        fmt.print_error(f"Profile '{profile}' not found")
        return

    if not yes:
        if not click.confirm(f"Delete profile '{profile}'?"):
            fmt.print_info("Cancelled")
            return

    cfg.remove_profile(profile)
    fmt.print_success(f"Profile '{profile}' deleted")


@config_group.command("use")
@click.argument("profile")
@click.pass_context
def config_use(ctx: click.Context, profile: str):
    """Switch active profile.

    Examples:
        jcli config use prod
        jcli config use dev
    """
    cfg = _get_config(ctx)
    fmt = _get_formatter(ctx)

    try:
        cfg.set_active_profile(profile)
    except ProfileNotFoundError:
        fmt.print_error(f"Profile '{profile}' not found")
        profiles = cfg.list_profiles()
        if profiles:
            fmt.print_info(f"Available profiles: {', '.join(profiles.keys())}")
        return

    fmt.print_success(f"Active profile set to '{profile}'")


def register(group: click.Group) -> None:
    """Register config commands with the main CLI group."""
    group.add_command(config_group, "config")
