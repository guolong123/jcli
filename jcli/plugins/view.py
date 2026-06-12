"""Jenkins View management commands."""

from __future__ import annotations

import json
from pathlib import Path

import click

from jcli.cli_helpers import get_client, get_formatter
from jcli.sdk.view import create_view as sdk_create_view
from jcli.sdk.view import delete_view as sdk_delete_view
from jcli.sdk.view import get_view as sdk_get_view
from jcli.sdk.view import list_views as sdk_list_views
from jcli.sdk.view import update_view as sdk_update_view


def _format_output(ctx: click.Context, data: object) -> str:
    """Format data according to the user-specified output format."""
    ctx_obj = ctx.obj or {}
    fmt = ctx_obj.get("format", "table")

    if fmt == "json":
        return json.dumps(data, indent=2, ensure_ascii=False)

    if fmt == "yaml":
        import yaml

        return yaml.dump(data, default_flow_style=False, allow_unicode=True)

    # Default: table-like plain text
    return str(data)


# ------------------------------------------------------------------
# Click command group
# ------------------------------------------------------------------


@click.group("view", help="Manage Jenkins views.")
def view_group():
    """View management commands."""


@view_group.command("list")
@click.pass_context
def view_list(ctx: click.Context) -> None:
    """List all Jenkins views."""
    client = get_client(ctx)
    views = sdk_list_views(client)

    # Build table output
    ctx_obj = ctx.obj or {}
    if ctx_obj.get("format", "table") == "table":
        if not views:
            click.echo("No views found.")
            return
        for v in views:
            job_count = len(v.get("jobs", []))
            click.echo(f"  {v['name']} ({job_count} jobs)")
        return

    click.echo(_format_output(ctx, views))


@view_group.command("get")
@click.argument("view_name", metavar="NAME")
@click.pass_context
def view_get(ctx: click.Context, view_name: str) -> None:
    """Get details for a Jenkins view."""
    client = get_client(ctx)
    data = sdk_get_view(client, view_name)

    # Table output: show key fields
    ctx_obj = ctx.obj or {}
    if ctx_obj.get("format", "table") == "table":
        click.echo(f"Name:        {data.get('name', view_name)}")
        click.echo(f"URL:         {data.get('url', '')}")
        click.echo(f"Description: {data.get('description', '')}")
        jobs = data.get("jobs", [])
        if jobs:
            click.echo("Jobs:")
            for j in jobs:
                click.echo(f"  - {j['name']}  [{j.get('color', 'unknown')}]")
        return

    click.echo(_format_output(ctx, data))


@view_group.command("create")
@click.argument("view_name", metavar="NAME")
@click.argument(
    "config_file",
    metavar="CONFIG_XML",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.pass_context
def view_create(ctx: click.Context, view_name: str, config_file: Path) -> None:
    """Create a new Jenkins view from an XML config file."""
    xml_data = config_file.read_text(encoding="utf-8")

    client = get_client(ctx)
    sdk_create_view(client, view_name, xml_data)
    click.echo(f"View '{view_name}' created successfully.")


@view_group.command("update")
@click.argument("view_name")
@click.argument("config_file", type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def update_view_cmd(ctx, view_name, config_file):
    """Update a view's configuration from an XML file."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config_xml = f.read()
        sdk_update_view(client, view_name, config_xml)
        fmt.print_success(f"View '{view_name}' updated.")
    except Exception as exc:
        fmt.print_error(str(exc))


@view_group.command("delete")
@click.argument("view_name", metavar="NAME")
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt.",
)
@click.pass_context
def view_delete(ctx: click.Context, view_name: str, yes: bool) -> None:
    """Delete a Jenkins view."""
    if not yes:
        click.confirm(
            f"Are you sure you want to delete view '{view_name}'?",
            abort=True,
        )

    client = get_client(ctx)
    sdk_delete_view(client, view_name)
    click.echo(f"View '{view_name}' deleted successfully.")


def register(parent_group: click.Group) -> None:
    """Register the view subgroup under the parent Click group."""
    parent_group.add_command(view_group)
