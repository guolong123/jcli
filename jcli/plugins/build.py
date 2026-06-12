"""Jenkins Build management commands."""

from __future__ import annotations

import click

from jcli.cli_helpers import get_client, get_formatter
from jcli.sdk.build import (
    cancel_queue_item,
    get_build,
    get_build_artifacts,
    get_build_log,
    get_builds,
    get_queue,
    stop_build,
    trigger_build,
)
from jcli.sdk.exceptions import JenkinsError


def _parse_params(raw_params: tuple[str, ...]) -> dict[str, str]:
    """Parse ``KEY=VAL`` strings into a dict."""
    params: dict[str, str] = {}
    for item in raw_params:
        if "=" not in item:
            raise click.BadParameter(f"Invalid parameter format: {item} (expected KEY=VAL)")
        key, _, value = item.partition("=")
        params[key.strip()] = value.strip()
    return params


# ------------------------------------------------------------------
# Build group
# ------------------------------------------------------------------


@click.group("build", help="Manage Jenkins builds.")
def build_group():
    """Build management commands."""


@build_group.command("trigger")
@click.argument("job_name")
@click.option(
    "--params", "-p",
    multiple=True,
    help="Build parameters as KEY=VAL pairs. Repeatable.",
)
@click.pass_context
def trigger(ctx: click.Context, job_name: str, params: tuple[str, ...]):
    """Trigger a new build for JOB_NAME.

    Use --params/-p KEY=VAL to pass build parameters (repeat for multiple).
    """
    client = get_client(ctx)
    fmt = get_formatter(ctx)
    try:
        param_dict = _parse_params(params) if params else None
        result = trigger_build(client, job_name, param_dict)
        fmt.print_success(f"Build triggered for {job_name}")
        fmt.print_json(result)
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1)


@build_group.command("list")
@click.argument("job_name")
@click.option("--limit", "-n", default=10, type=int, help="Maximum builds to show.")
@click.pass_context
def list_builds(ctx: click.Context, job_name: str, limit: int):
    """List recent builds for JOB_NAME."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)
    try:
        builds = get_builds(client, job_name, limit=limit)
        if not builds:
            fmt.print_info(f"No builds found for {job_name}")
            return

        headers = ["Number", "Result", "Timestamp", "Duration", "Building"]
        rows = [
            [
                b.get("number", ""),
                str(b.get("result") or "IN PROGRESS"),
                str(b.get("timestamp", "")),
                str(b.get("duration", "")),
                str(b.get("building", False)),
            ]
            for b in builds
        ]
        fmt.print_table(headers, rows, title=f"Builds for {job_name}")
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1)


@build_group.command("get")
@click.argument("job_name")
@click.argument("number", type=int)
@click.pass_context
def get_build_cmd(ctx: click.Context, job_name: str, number: int):
    """Show details for a specific build."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)
    try:
        build = get_build(client, job_name, number)
        fmt.print_json(build)
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1)


@build_group.command("log")
@click.argument("job_name")
@click.argument("number", type=int)
@click.pass_context
def log_cmd(ctx: click.Context, job_name: str, number: int):
    """Show console log for a build."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)
    try:
        log_text = get_build_log(client, job_name, number)
        fmt.console.print(log_text)
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1)


@build_group.command("stop")
@click.argument("job_name")
@click.argument("number", type=int)
@click.pass_context
def stop_cmd(ctx: click.Context, job_name: str, number: int):
    """Stop a running build."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)
    try:
        stop_build(client, job_name, number)
        fmt.print_success(f"Build {job_name}#{number} stopped")
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1)


@build_group.command("queue")
@click.pass_context
def queue_cmd(ctx: click.Context):
    """Show the current Jenkins build queue."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)
    try:
        items = get_queue(client)
        if not items:
            fmt.print_info("Build queue is empty")
            return

        headers = ["ID", "Task", "Why", "In Queue Since"]
        rows = [
            [
                str(item.get("id", "")),
                str(item.get("task", {}).get("name", "")),
                str(item.get("why", "")),
                str(item.get("inQueueSince", "")),
            ]
            for item in items
        ]
        fmt.print_table(headers, rows, title="Build Queue")
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1)


@build_group.command("artifacts")
@click.argument("job_name")
@click.argument("build_number")
@click.pass_context
def artifacts_cmd(ctx: click.Context, job_name: str, build_number: str):
    """List artifacts for a build."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)
    try:
        data = get_build_artifacts(client, job_name, build_number)
        artifacts = data.get("artifacts", [])
        if not artifacts:
            fmt.print_info("No artifacts found.")
            return
        headers = ["File Name", "Relative Path"]
        rows = [[a["fileName"], a["relativePath"]] for a in artifacts]
        fmt.print_table(headers, rows, title=f"Artifacts: {job_name} #{build_number}")
    except Exception as exc:
        fmt.print_error(str(exc))


def register(parent_group: click.Group):
    """Register the build subgroup under the parent Click group."""
    parent_group.add_command(build_group)
