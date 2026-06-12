"""Jenkins Node management commands."""

from __future__ import annotations

import click

from jcli.cli_helpers import get_client, get_formatter
from jcli.sdk.node import create_node, delete_node, get_node, list_nodes, toggle_offline


@click.group("node", help="Manage Jenkins nodes (agents).")
def node_group():
    """Node management commands."""


@node_group.command("list")
@click.pass_context
def list_nodes_cmd(ctx: click.Context):
    """List all Jenkins nodes."""
    fmt = get_formatter(ctx)
    client = get_client(ctx)

    try:
        nodes = list_nodes(client)
        if nodes:
            headers = ["Name", "Online", "Temporarily Offline", "Architecture"]
            rows = [
                [
                    n.get("displayName", "?"),
                    "Yes" if not n.get("offline", True) else "No",
                    "Yes" if n.get("temporarilyOffline", False) else "No",
                    n.get("monitorData", {}).get("hudson.node_monitors.ArchitectureMonitor", "?"),
                ]
                for n in nodes
            ]
            fmt.print_table(headers, rows, title="Jenkins Nodes")
        else:
            fmt.print_info("No nodes found.")
    except Exception as exc:
        fmt.print_error(str(exc))


@node_group.command("get")
@click.argument("name")
@click.pass_context
def get_node_cmd(ctx: click.Context, name: str):
    """Get details of a specific node."""
    fmt = get_formatter(ctx)
    client = get_client(ctx)

    try:
        node = get_node(client, name)
        if fmt.format_type == "json":
            fmt.print_json(node)
        else:
            headers = ["Property", "Value"]
            rows = [
                ["Display Name", node.get("displayName", "?")],
                ["Description", node.get("description", "") or "-"],
                ["Offline", "Yes" if node.get("offline", True) else "No"],
                ["Temporarily Offline", "Yes" if node.get("temporarilyOffline", False) else "No"],
                ["Num Executors", str(node.get("numExecutors", "?"))],
                ["Idle", "Yes" if node.get("idle", False) else "No"],
                ["JNLP Agent", "Yes" if node.get("jnlpAgent", False) else "No"],
            ]
            # Add monitor data if available
            monitor = node.get("monitorData", {})
            if monitor:
                for key, val in monitor.items():
                    if key.startswith("hudson.node_monitors."):
                        label = key.replace("hudson.node_monitors.", "")
                        rows.append([f"Monitor: {label}", str(val)])
            fmt.print_table(headers, rows, title=f"Node: {name}")
    except Exception as exc:
        fmt.print_error(str(exc))


@node_group.command("delete")
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt.")
@click.pass_context
def delete_node_cmd(ctx: click.Context, name: str, force: bool):
    """Delete a Jenkins node (agent)."""
    fmt = get_formatter(ctx)
    client = get_client(ctx)

    if not force:
        if not click.confirm(f"Are you sure you want to delete node '{name}'?"):
            fmt.print_info("Delete cancelled.")
            return

    try:
        delete_node(client, name)
        fmt.print_success(f"Node '{name}' deleted successfully.")
    except Exception as exc:
        fmt.print_error(str(exc))


@node_group.command("toggle")
@click.argument("name")
@click.option("--message", "-m", default="", help="Reason for toggling offline/online.")
@click.pass_context
def toggle_node_cmd(ctx: click.Context, name: str, message: str):
    """Toggle a node offline or online."""
    fmt = get_formatter(ctx)
    client = get_client(ctx)

    try:
        toggle_offline(client, name, msg=message)
        fmt.print_success(f"Node '{name}' toggled successfully.")
    except Exception as exc:
        fmt.print_error(str(exc))


@node_group.command("create")
@click.argument("name")
@click.option("--executors", type=int, default=1, help="Number of executors (default: 1).")
@click.option("--remote-fs", default="/tmp", help="Remote filesystem root (default: /tmp).")
@click.option("--labels", default="", help="Node labels.")
@click.pass_context
def create_node_cmd(ctx: click.Context, name: str, executors: int, remote_fs: str, labels: str):
    """Create a new Jenkins agent node."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)
    try:
        create_node(client, name, num_executors=executors, remote_fs=remote_fs, labels=labels)
        fmt.print_success(f"Node '{name}' created.")
    except Exception as exc:
        fmt.print_error(str(exc))


def register(parent_group):
    """Register the node subgroup under the parent Click group."""
    parent_group.add_command(node_group)
