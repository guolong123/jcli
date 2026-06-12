"""Jenkins System SDK functions.

All functions take a :class:`~jcli.sdk.client.JenkinsClient` as the first argument.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from jcli.sdk.client import JenkinsClient

# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def get_system_info(client: "JenkinsClient") -> dict[str, Any]:
    """Get Jenkins system information.

    Calls ``GET /api/json`` and extracts version from the ``X-Jenkins``
    response header.

    Args:
        client: Authenticated Jenkins API client.

    Returns:
        Dictionary with keys:
        - ``version``: Jenkins version string (from ``X-Jenkins`` header).
        - ``num_executors``: Total number of executors.
        - ``mode``: Executor mode (e.g. ``NORMAL``, ``EXCLUSIVE``).
        - ``quietingDown``: Whether Jenkins is in quiet-down mode.
        - ``slaveAgentPort``: Port for JNLP agents.
        - ``num_nodes``: Total number of connected nodes (from ``computer``).
        - ``num_jobs``: Total number of jobs.
        - ``raw``: Full API response data.
    """
    resp = client.request("GET", "/api/json")
    data: dict[str, Any] = resp.json()

    version = resp.headers.get("X-Jenkins", "unknown")

    # Count nodes from computer list if available
    num_nodes = 0
    computer = data.get("computer", [])
    if isinstance(computer, list):
        num_nodes = len(computer)

    return {
        "version": version,
        "num_executors": data.get("numExecutors", 0),
        "mode": data.get("mode", ""),
        "quietingDown": data.get("quietingDown", False),
        "slaveAgentPort": data.get("slaveAgentPort", 0),
        "num_nodes": num_nodes,
        "num_jobs": len(data.get("jobs", [])),
        "raw": data,
    }


def safe_restart(client: "JenkinsClient") -> bool:
    """Trigger a safe restart of Jenkins.

    Calls ``POST /safeRestart``. Jenkins waits for running builds to
    complete before restarting.

    Args:
        client: Authenticated Jenkins API client.

    Returns:
        ``True`` on success (HTTP 200/302).
    """
    resp = client.request("POST", "/safeRestart")
    return resp.ok


def quiet_down(client: "JenkinsClient", reason: str = "") -> bool:
    """Put Jenkins into quiet-down mode.

    In quiet-down mode, Jenkins stops scheduling new builds. Running
    builds continue until finished.  Calls ``POST /quietDown``.

    Args:
        client: Authenticated Jenkins API client.
        reason: Optional reason shown on the quiet-down banner.

    Returns:
        ``True`` on success (HTTP 200/302).
    """
    params: dict[str, str] | None = None
    if reason:
        params = {"reason": reason}
    resp = client.request("POST", "/quietDown", params=params)
    return resp.ok


def cancel_quiet_down(client: "JenkinsClient") -> bool:
    """Cancel quiet-down mode, allowing Jenkins to resume scheduling builds.

    Calls ``POST /cancelQuietDown``.

    Args:
        client: Authenticated Jenkins API client.

    Returns:
        ``True`` on success (HTTP 200/302).
    """
    resp = client.request("POST", "/cancelQuietDown")
    return resp.ok


def run_script(client: "JenkinsClient", script: str) -> Any:
    """Execute a Groovy script on the Jenkins server.

    Calls ``POST /scriptText`` with form-encoded script content.

    Args:
        client: Jenkins API client.
        script: Groovy script text.

    Returns:
        Script output as text.
    """
    resp = client.post_data("/scriptText", data={"script": script})
    return resp.text


def get_system_load(client: "JenkinsClient") -> dict[str, Any]:
    """Get current system load statistics.

    Calls ``GET /queue/api/json`` for the build queue and
    ``GET /computer/api/json`` for executor usage.

    Args:
        client: Authenticated Jenkins API client.

    Returns:
        Dictionary with keys:
        - ``queue_length``: Number of items in the build queue.
        - ``total_executors``: Total executors across all nodes.
        - ``busy_executors``: Currently busy executors.
        - ``idle_executors``: Currently idle executors.
    """
    queue_data = client.get_json("/queue/api/json")
    queue_items = queue_data.get("items", [])
    queue_length = len(queue_items) if isinstance(queue_items, list) else 0

    computer_data = client.get_json("/computer/api/json")
    computers = computer_data.get("computer", [])
    total_executors = 0
    busy_executors = 0
    if isinstance(computers, list):
        for c in computers:
            total_executors += c.get("numExecutors", 0)
            busy = c.get("busyExecutors", 0)
            if busy:
                busy_executors += busy

    idle_executors = total_executors - busy_executors

    return {
        "queue_length": queue_length,
        "total_executors": total_executors,
        "busy_executors": busy_executors,
        "idle_executors": idle_executors,
    }


def list_users(client: "JenkinsClient") -> Any:
    """List all Jenkins users.

    Calls ``GET /asynchPeople/api/json``.

    Args:
        client: Authenticated Jenkins API client.

    Returns:
        Parsed JSON with users list.
    """
    return client.get_json("/asynchPeople/api/json")


def generate_token(
    client: "JenkinsClient",
    username: str,
    token_name: str = "jcli-generated",
) -> Any:
    """Generate a new API token for a user.

    Calls ``POST /user/{name}/descriptorByName/jenkins.security.ApiTokenProperty/generateNewToken``.

    Args:
        client: Authenticated Jenkins API client.
        username: Jenkins username.
        token_name: Name/label for the new token.

    Returns:
        Parsed JSON with token data including the token value.
    """
    path = f"/user/{username}/descriptorByName/jenkins.security.ApiTokenProperty/generateNewToken"
    data = {"newTokenName": token_name}
    return client.post_data(path, data=data).json()
