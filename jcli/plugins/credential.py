"""Jenkins Credential management commands."""

import sys
from pathlib import Path
from typing import Any

import click

from jcli.cli_helpers import get_client, get_formatter
from jcli.sdk.credential import (
    create_credential,
    delete_credential,
    get_credential,
    list_credentials,
    update_credential,
)


def _display_result(ctx: click.Context, result: Any) -> None:
    """Display result using the configured formatter.

    If result is a dict with a ``credentials`` key, render as a table.
    If result is a dict, pretty-print.
    Otherwise, print as JSON.
    """
    formatter = get_formatter(ctx)

    if isinstance(result, dict) and "credentials" in result:
        creds = result["credentials"]
        if not creds:
            formatter.print_info("No credentials found.")
            return
        rows = [
            [c.get("id", ""), c.get("typeName", ""), c.get("description", "")]
            for c in creds
        ]
        formatter.print_table(
            headers=["ID", "Type", "Description"],
            rows=rows,
            title="Credentials",
        )
    else:
        formatter.print_json(result)


@click.group("credential", help="Manage Jenkins credentials.")
def credential_group():
    """Credential management commands."""


@credential_group.command("list")
@click.option(
    "--store", "-s", default="system", help="Credential store ID (default: system)."
)
@click.option(
    "--domain", "-d", default="_", help="Credential domain ID (default: _)."
)
@click.pass_context
def cmd_list(ctx: click.Context, store: str, domain: str) -> None:
    """List Jenkins credentials."""
    client = get_client(ctx)
    try:
        result = list_credentials(client, store=store, domain=domain, depth=1)
        _display_result(ctx, result)
    except Exception as exc:
        get_formatter(ctx).print_error(str(exc))
        sys.exit(1)


@credential_group.command("get")
@click.argument("cred_id")
@click.option(
    "--store", "-s", default="system", help="Credential store ID (default: system)."
)
@click.pass_context
def cmd_get(ctx: click.Context, cred_id: str, store: str) -> None:
    """Get credential details."""
    client = get_client(ctx)
    try:
        result = get_credential(client, cred_id=cred_id, store=store)
        get_formatter(ctx).print_json(result)
    except Exception as exc:
        get_formatter(ctx).print_error(str(exc))
        sys.exit(1)


@credential_group.command("create")
@click.argument("cred_id")
@click.argument(
    "config_xml",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--store", "-s", default="system", help="Credential store ID (default: system)."
)
@click.option(
    "--domain", "-d", default="_", help="Credential domain ID (default: _)."
)
@click.pass_context
def cmd_create(
    ctx: click.Context,
    cred_id: str,
    config_xml: Path,
    store: str,
    domain: str,
) -> None:
    """Create a credential from an XML config file.

    CRED_ID is the credential ID (ignored by Jenkins API, used for reference).
    CONFIG_XML is a path to the credential XML file.

    The XML must follow Jenkins' XStream format for the target credential type.
    Example for UsernamePasswordCredentialsImpl:

    \\b
    <com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>
      <scope>GLOBAL</scope>
      <id>my-cred-id</id>
      <description>My credential</description>
      <username>admin</username>
      <password>secret</password>
    </com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>
    """
    client = get_client(ctx)
    formatter = get_formatter(ctx)
    try:
        xml_data = config_xml.read_text(encoding="utf-8")
        create_credential(client, xml_data=xml_data, store=store, domain=domain)
        formatter.print_success(f"Credential created in store '{store}' domain '{domain}'.")
    except Exception as exc:
        formatter.print_error(str(exc))
        sys.exit(1)


@credential_group.command("update")
@click.argument("cred_id")
@click.argument(
    "config_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--store", "-s", default="system", help="Credential store ID (default: system)."
)
@click.pass_context
def cmd_update(
    ctx: click.Context,
    cred_id: str,
    config_file: Path,
    store: str,
) -> None:
    """Update a credential from an XML config file.

    CRED_ID is the credential ID to update.
    CONFIG_FILE is a path to the credential XML file.

    The XML must follow Jenkins' XStream format for the target credential type.
    Example for UsernamePasswordCredentialsImpl:

    \\b
    <com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>
      <scope>GLOBAL</scope>
      <id>my-cred-id</id>
      <description>My credential</description>
      <username>admin</username>
      <password>new-secret</password>
    </com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>
    """
    client = get_client(ctx)
    formatter = get_formatter(ctx)
    try:
        xml_data = config_file.read_text(encoding="utf-8")
        update_credential(client, cred_id=cred_id, xml_data=xml_data, store=store)
        formatter.print_success(f"Credential '{cred_id}' updated in store '{store}'.")
    except Exception as exc:
        formatter.print_error(str(exc))
        sys.exit(1)


@credential_group.command("delete")
@click.argument("cred_id")
@click.option(
    "--store", "-s", default="system", help="Credential store ID (default: system)."
)
@click.option(
    "--force", "-f", is_flag=True, default=False, help="Skip confirmation prompt."
)
@click.pass_context
def cmd_delete(
    ctx: click.Context, cred_id: str, store: str, force: bool
) -> None:
    """Delete a credential."""
    if not force:
        click.confirm(
            f"Delete credential '{cred_id}' from store '{store}'?",
            abort=True,
        )

    client = get_client(ctx)
    formatter = get_formatter(ctx)
    try:
        delete_credential(client, cred_id=cred_id, store=store)
        formatter.print_success(f"Credential '{cred_id}' deleted.")
    except Exception as exc:
        formatter.print_error(str(exc))
        sys.exit(1)


def register(parent_group: click.Group) -> None:
    """Register the credential subgroup under the parent Click group."""
    parent_group.add_command(credential_group)
