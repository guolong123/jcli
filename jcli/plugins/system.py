"""Jenkins System management commands."""

import logging

import click

from jcli.cli_helpers import get_client, get_formatter
from jcli.sdk.client import JenkinsClient
from jcli.sdk.config import Config
from jcli.sdk.exceptions import JenkinsConfigError
from jcli.sdk.system import (
    cancel_quiet_down,
    generate_token,
    get_system_info,
    get_system_load,
    list_users,
    quiet_down,
    run_script,
    safe_restart,
)

logger = logging.getLogger(__name__)


@click.group("system", help="Jenkins system information and management.")
def system_group():
    """System management commands."""


@system_group.command("info")
@click.pass_context
def system_info(ctx: click.Context):
    """Show Jenkins system information."""
    formatter = get_formatter(ctx)
    client = get_client(ctx)

    info = get_system_info(client)

    formatter.print_info(f"Jenkins {info['version']}")
    formatter.print_info(f"Mode: {info['mode']}")
    formatter.print_info(f"Quieting down: {info['quietingDown']}")

    rows = [
        ("Executors", str(info["num_executors"])),
        ("Nodes", str(info["num_nodes"])),
        ("Jobs", str(info["num_jobs"])),
        ("Slave Agent Port", str(info["slaveAgentPort"])),
    ]
    formatter.print_table(
        headers=("Property", "Value"),
        rows=rows,
        title="System Overview",
    )


@system_group.command("restart")
@click.pass_context
def system_restart(ctx: click.Context):
    """Trigger a safe restart of Jenkins."""
    formatter = get_formatter(ctx)
    client = get_client(ctx)

    if safe_restart(client):
        formatter.print_success("Safe restart initiated.")
    else:
        formatter.print_error("Failed to initiate safe restart.")


@system_group.command("quiet-down")
@click.option("--reason", "-r", default="", help="Reason for quiet-down.")
@click.pass_context
def system_quiet_down(ctx: click.Context, reason: str):
    """Put Jenkins into quiet-down mode."""
    formatter = get_formatter(ctx)
    client = get_client(ctx)

    if quiet_down(client, reason=reason):
        formatter.print_success("Jenkins is now in quiet-down mode.")
        if reason:
            formatter.print_info(f"Reason: {reason}")
    else:
        formatter.print_error("Failed to enter quiet-down mode.")


@system_group.command("cancel-quiet-down")
@click.pass_context
def system_cancel_quiet_down(ctx: click.Context):
    """Cancel quiet-down mode."""
    formatter = get_formatter(ctx)
    client = get_client(ctx)

    if cancel_quiet_down(client):
        formatter.print_success("Quiet-down mode cancelled.")
    else:
        formatter.print_error("Failed to cancel quiet-down mode.")


@system_group.command("load")
@click.pass_context
def system_load(ctx: click.Context):
    """Show current system load (queue length, executor usage)."""
    formatter = get_formatter(ctx)
    client = get_client(ctx)

    load = get_system_load(client)

    rows = [
        ("Queue Length", str(load["queue_length"])),
        ("Total Executors", str(load["total_executors"])),
        ("Busy Executors", str(load["busy_executors"])),
        ("Idle Executors", str(load["idle_executors"])),
    ]
    formatter.print_table(
        headers=("Metric", "Value"),
        rows=rows,
        title="System Load",
    )


@system_group.command("script")
@click.argument("script")
@click.pass_context
def script_cmd(ctx: click.Context, script: str):
    """Execute a Groovy script on the Jenkins server.

    SCRIPT is the Groovy script text to execute.
    """
    client = get_client(ctx)
    fmt = get_formatter(ctx)
    try:
        result = run_script(client, script)
        print(result)
    except Exception as exc:
        fmt.print_error(str(exc))


@system_group.command("users")
@click.pass_context
def users_cmd(ctx: click.Context):
    """List all Jenkins users."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)
    try:
        data = list_users(client)
        users = data.get("users", [])
        if not users:
            fmt.print_info("No users found.")
            return
        user_ids = [u["user"]["fullName"] for u in users]
        fmt.print_json(user_ids)
    except Exception as exc:
        fmt.print_error(str(exc))


@system_group.command("token")
@click.argument("username")
@click.option("--name", "-n", default="jcli-generated", help="Token name/label.")
@click.pass_context
def token_cmd(ctx: click.Context, username: str, name: str):
    """Generate a new API token for a user."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)
    try:
        result = generate_token(client, username, token_name=name)
        fmt.print_json(result)
        fmt.print_success(f"Token generated for user '{username}'.")
    except Exception as exc:
        fmt.print_error(str(exc))


def register(parent_group):
    """Register the system subgroup under the parent Click group."""
    parent_group.add_command(system_group)
