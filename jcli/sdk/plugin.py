"""Jenkins Plugin management SDK functions."""

from __future__ import annotations

import logging
from typing import Any

from jcli.sdk.client import JenkinsClient
from jcli.sdk.exceptions import JenkinsAPIError, JenkinsNotFoundError

logger = logging.getLogger(__name__)

# Jenkins plugin manager API paths
PLUGIN_MANAGER_API = "/pluginManager/api/json"
INSTALL_PLUGINS_PATH = "/pluginManager/installNecessaryPlugins"

# Tree filter for listing plugins (essential fields only)
PLUGIN_LIST_TREE = "plugins[shortName,version,active,hasUpdate]"

# Tree filter for plugin details (richer fields)
PLUGIN_DETAIL_TREE = (
    "plugins[shortName,version,active,hasUpdate,longName,url,"
    "requiredCoreVersion,hasRequireRestart]"
)


def _build_install_xml(plugins_dict: dict[str, str | None]) -> str:
    """Build XML body for plugin installation request.

    Args:
        plugins_dict: Mapping of plugin shortName to optional version.
            e.g. {"git": "5.0.0", "workflow-aggregator": None}

    Returns:
        XML string for POST to /pluginManager/installNecessaryPlugins.
    """
    lines = ["<jenkins>"]
    for name, version in plugins_dict.items():
        if version:
            lines.append(f'  <install plugin="{name}@{version}" />')
        else:
            lines.append(f'  <install plugin="{name}" />')
    lines.append("</jenkins>")
    return "\n".join(lines)


def list_plugins(client: JenkinsClient) -> list[dict[str, Any]]:
    """Return a list of installed plugins with summary fields.

    URI: GET /pluginManager/api/json?tree=plugins[shortName,version,active,hasUpdate]

    Returns:
        List of plugin dicts with keys: shortName, version, active, hasUpdate.
    """
    data = client.get_json(
        PLUGIN_MANAGER_API,
        tree=PLUGIN_LIST_TREE,
    )
    logger.debug("list_plugins returned %d entries", len(data.get("plugins", [])))
    return data.get("plugins", [])


def get_plugin(client: JenkinsClient, short_name: str) -> dict[str, Any] | None:
    """Return details for a single plugin by shortName.

    Uses the full API response and filters locally to avoid additional round-trips.

    Args:
        client: Authenticated Jenkins client.
        short_name: Plugin short name (e.g. "git", "workflow-aggregator").

    Returns:
        Plugin detail dict, or None if not found.

    Raises:
        JenkinsNotFoundError: if no plugin matching short_name is found.
    """
    data = client.get_json(
        PLUGIN_MANAGER_API,
        tree=PLUGIN_DETAIL_TREE,
    )
    plugins: list[dict[str, Any]] = data.get("plugins", [])

    for p in plugins:
        if p.get("shortName") == short_name:
            return p

    raise JenkinsNotFoundError(
        f"Plugin '{short_name}' not found on server"
    )


def install_plugins(
    client: JenkinsClient,
    plugins_dict: dict[str, str | None],
) -> None:
    """Install one or more plugins (optionally with specific versions).

    URI: POST /pluginManager/installNecessaryPlugins

    The server will download and install the requested plugins.
    Restart may be required afterward.

    Args:
        client: Authenticated Jenkins client.
        plugins_dict: Mapping of {plugin_shortName: version_or_None}.
            If version is None, the latest version is installed.

    Raises:
        JenkinsAPIError: if the request fails.
    """
    if not plugins_dict:
        logger.warning("install_plugins called with empty dict, nothing to do")
        return

    xml_body = _build_install_xml(plugins_dict)
    logger.info("Installing plugins: %s", list(plugins_dict.keys()))
    logger.debug("Install XML: %s", xml_body)

    client.post_xml(INSTALL_PLUGINS_PATH, xml_body)


def check_plugin_updates(client: JenkinsClient) -> Any:
    """Check for plugin updates.

    Triggers Jenkins to check for available plugin updates.

    Args:
        client: Jenkins API client.

    Returns:
        Parsed JSON response with update information.
    """
    return client.post_data("/pluginManager/checkUpdates", data={}).json()


def uninstall_plugin(client: JenkinsClient, short_name: str) -> None:
    """Trigger uninstall of a plugin by its short name.

    URI: POST /pluginManager/plugin/{shortName}/doUninstall

    The server schedules the plugin for uninstall. A restart is typically required
    to complete the removal.

    Args:
        client: Authenticated Jenkins client.
        short_name: Plugin short name to uninstall.

    Raises:
        JenkinsAPIError: if the request fails.
    """
    path = f"/pluginManager/plugin/{short_name}/doUninstall"
    logger.info("Uninstalling plugin: %s", short_name)

    client.request("POST", path)
