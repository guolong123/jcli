"""Jenkins System management plugin: info, load, script, token methods."""
from cliyard.plugin import register_method


@register_method("jenkins_system_info")
def jenkins_system_info(params, http_client, config):
    """Get Jenkins system information.

    Calls GET /api/json and extracts version from X-Jenkins header.
    Aggregates executor count, mode, quieting down status, nodes, and jobs.

    Args:
        params: Dictionary (unused, empty body).
        http_client: Configured HttpClient instance.
        config: Plugin configuration (unused).

    Returns:
        Dictionary with version, num_executors, mode, quietingDown,
        slaveAgentPort, num_nodes, num_jobs.
    """
    resp = http_client.request("GET", "/api/json")
    data = resp.json()

    version = resp.headers.get("X-Jenkins", "unknown")

    # Count nodes from computer list
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
    }


@register_method("jenkins_system_load")
def jenkins_system_load(params, http_client, config):
    """Get current system load statistics.

    Aggregates queue length from /queue/api/json and executor usage
    from /computer/api/json.

    Args:
        params: Dictionary (unused, empty body).
        http_client: Configured HttpClient instance.
        config: Plugin configuration (unused).

    Returns:
        Dictionary with queue_length, total_executors, busy_executors,
        idle_executors.
    """
    queue_data = http_client.request("GET", "/queue/api/json").json()
    queue_items = queue_data.get("items", [])
    queue_length = len(queue_items) if isinstance(queue_items, list) else 0

    computer_data = http_client.request("GET", "/computer/api/json").json()
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


@register_method("jenkins_system_script")
def jenkins_system_script(params, http_client, config):
    """Execute a Groovy script on the Jenkins server.

    Posts form-encoded script to /scriptText.

    Args:
        params: Dictionary with 'script' key containing Groovy code.
        http_client: Configured HttpClient instance.
        config: Plugin configuration (unused).

    Returns:
        Script output as text.
    """
    script = params.get("script", "")
    if not script:
        return {"error": "No script provided"}

    resp = http_client.request(
        "POST",
        "/scriptText",
        data={"script": script},
    )
    return {"output": resp.text}


@register_method("jenkins_system_token")
def jenkins_system_token(params, http_client, config):
    """Generate a new API token for a user.

    Posts form-encoded newTokenName to
    /user/{username}/descriptorByName/jenkins.security.ApiTokenProperty/generateNewToken

    Args:
        params: Dictionary with 'username' and 'token_name' keys.
        http_client: Configured HttpClient instance.
        config: Plugin configuration (unused).

    Returns:
        Parsed JSON with token data including the token value.
    """
    username = params.get("username", "")
    token_name = params.get("token_name", "jcli-generated")

    if not username:
        return {"error": "No username provided"}

    path = f"/user/{username}/descriptorByName/jenkins.security.ApiTokenProperty/generateNewToken"
    resp = http_client.request(
        "POST",
        path,
        data={"newTokenName": token_name},
    )
    return resp.json()
