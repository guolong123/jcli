"""Jenkins Node (Agent) SDK functions.

All functions take a :class:`~jcli.sdk.client.JenkinsClient` as the first argument.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

if TYPE_CHECKING:
    from jcli.sdk.client import JenkinsClient

# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def list_nodes(client: "JenkinsClient") -> list[dict[str, Any]]:
    """List all Jenkins nodes (built-in node + agents).

    Calls ``GET /computer/api/json``.

    Args:
        client: Authenticated Jenkins API client.

    Returns:
        List of node dictionaries, each containing ``displayName``,
        ``offline``, ``temporarilyOffline``, and other fields.
    """
    data = client.get_json("/computer/api/json")
    return data.get("computer", [])


def get_node(client: "JenkinsClient", name: str) -> dict[str, Any]:
    """Get details for a specific node.

    Calls ``GET /computer/{name}/api/json``.

    Args:
        client: Authenticated Jenkins API client.
        name: Node display name (e.g. ``"built-in"``, ``"agent-1"``).

    Returns:
        Node detail dictionary.
    """
    return client.get_json(f"/computer/{quote(name, safe='')}/api/json")


def delete_node(client: "JenkinsClient", name: str) -> bool:
    """Delete a node (agent) from Jenkins.

    Calls ``POST /computer/{name}/doDelete``. The built-in node
    cannot be deleted.

    Args:
        client: Authenticated Jenkins API client.
        name: Node display name to delete.

    Returns:
        ``True`` on success (HTTP 200/302).
    """
    resp = client.request("POST", f"/computer/{quote(name, safe='')}/doDelete")
    return resp.ok


def toggle_offline(
    client: "JenkinsClient",
    name: str,
    msg: str = "",
) -> bool:
    """Toggle a node's offline/online state.

    If the node is currently online, this marks it temporarily offline.
    If already temporarily offline, this brings it back online.
    Calls ``POST /computer/{name}/toggleOffline``.

    Args:
        client: Authenticated Jenkins API client.
        name: Node display name.
        msg: Optional offline message (shown when marking offline).

    Returns:
        ``True`` on success (HTTP 200/302).
    """
    data: dict[str, Any] = {}
    if msg:
        data["offlineMessage"] = msg
    resp = client.post_data(f"/computer/{quote(name, safe='')}/toggleOffline", data=data)
    return resp.ok


def create_node(
    client: "JenkinsClient",
    name: str,
    num_executors: int = 1,
    remote_fs: str = "/tmp",
    labels: str = "",
    launch_method: str = "hudson.slaves.JNLPLauncher",
) -> Any:
    """Create a new Jenkins agent node.

    Uses form submission to create a DumbSlave node via
    ``POST /computer/doCreateItem``.

    Args:
        client: Authenticated Jenkins API client.
        name: Node display name.
        num_executors: Number of executors (default: 1).
        remote_fs: Remote filesystem root (default: ``/tmp``).
        labels: Node labels string.
        launch_method: Stapler launch method class name.

    Returns:
        ``requests.Response`` from the creation POST.
    """
    data = {
        "name": name,
        "type": "hudson.slaves.DumbSlave",
        "json": json.dumps({
            "name": name,
            "nodeDescription": "",
            "numExecutors": str(num_executors),
            "remoteFS": remote_fs,
            "labelString": labels,
            "mode": "NORMAL",
            "type": "hudson.slaves.DumbSlave",
            "retentionStrategy": {"stapler-class": "hudson.slaves.RetentionStrategy$Always"},
            "nodeProperties": {"stapler-class-bag": "true"},
            "launcher": {"stapler-class": launch_method},
        }),
    }
    return client.request(
        "POST",
        "/computer/doCreateItem",
        params={"name": name, "type": "hudson.slaves.DumbSlave"},
        data=data,
    )
