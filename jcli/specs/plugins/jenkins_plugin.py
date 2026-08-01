"""Jenkins Plugin management plugin: get plugin details and install plugins."""
from cliyard.plugin import register_method


@register_method("jenkins_plugin_get")
def jenkins_plugin_get(params, http_client, config):
    """Get details for a single plugin by short name.

    Fetches all plugins and filters locally to find the matching one.

    Args:
        params: Dictionary containing 'short_name' key.
        http_client: Configured HttpClient instance.
        config: Plugin configuration (unused).

    Returns:
        Plugin detail dict, or error dict if not found.
    """
    short_name = params.get("short_name", "")
    if not short_name:
        return {"error": "No plugin name provided"}

    # Fetch all plugins with detailed info
    resp = http_client.request(
        "GET",
        "/pluginManager/api/json",
        query_params={"tree": "plugins[shortName,version,active,hasUpdate,longName,url,requiredCoreVersion,hasRequireRestart]"}
    )
    data = resp.json()
    plugins = data.get("plugins", [])

    for p in plugins:
        if p.get("shortName") == short_name:
            return p

    return {"error": f"Plugin '{short_name}' not found"}


@register_method("jenkins_plugin_install")
def jenkins_plugin_install(params, http_client, config):
    """Install one or more plugins (optionally with specific versions).

    Args:
        params: Dictionary containing 'plugins' key with list of plugin specs.
                Each spec can be 'name' or 'name@version'.
        http_client: Configured HttpClient instance.
        config: Plugin configuration (unused).

    Returns:
        Success message or error dict.
    """
    plugins_list = params.get("plugins", [])
    if not plugins_list:
        return {"error": "No plugins specified"}

    lines = ["<jenkins>"]
    for spec in plugins_list:
        if "@" in spec:
            name, version = spec.split("@", 1)
            lines.append(f'  <install plugin="{name}@{version}" />')
        else:
            lines.append(f'  <install plugin="{spec}" />')
    lines.append("</jenkins>")
    xml_body = "\n".join(lines)

    headers = {"Content-Type": "application/xml"}
    resp = http_client.request(
        "POST",
        "/pluginManager/installNecessaryPlugins",
        data=xml_body.encode("utf-8"),
        headers=headers
    )

    if resp.status_code == 200:
        return {"status": "success", "message": "Plugins scheduled for installation"}
    else:
        return {"error": f"Install failed with status {resp.status_code}"}