"""SDK functions for Jenkins View management."""

from __future__ import annotations

from typing import Any

from jcli.sdk.client import JenkinsClient
from jcli.sdk.exceptions import JenkinsAPIError


def list_views(client: JenkinsClient) -> list[dict[str, Any]]:
    """List all views on the Jenkins server.

    Args:
        client: Authenticated Jenkins client.

    Returns:
        List of view dicts, each with ``name``, ``url``, and ``jobs`` keys.

    Raises:
        JenkinsAPIError: If the API request fails.
    """
    data = client.get_json("/api/json", tree="views[name,url,jobs[name]]")
    return data.get("views", [])


def get_view(client: JenkinsClient, name: str) -> dict[str, Any]:
    """Get details for a single Jenkins view.

    Args:
        client: Authenticated Jenkins client.
        name: View name.

    Returns:
        View detail dict.

    Raises:
        JenkinsAPIError: If the API request fails.
        JenkinsNotFoundError: If the view doesn't exist.
    """
    return client.get_json(f"/view/{name}/api/json")


def create_view(
    client: JenkinsClient,
    name: str,
    config_xml: str,
) -> None:
    """Create a new Jenkins view.

    Args:
        client: Authenticated Jenkins client.
        name: View name to create.
        config_xml: XML configuration for the view.

    Raises:
        JenkinsAPIError: If the API request fails (e.g. view already exists).
    """
    client.post_xml(f"/createView?name={name}", config_xml)


def update_view(
    client: JenkinsClient,
    name: str,
    config_xml: str | bytes,
) -> Any:
    """Update a view's configuration.

    Args:
        client: Jenkins API client.
        name: View name.
        config_xml: New XML configuration.

    Returns:
        Response from Jenkins.

    Raises:
        JenkinsAPIError: If the API request fails.
    """
    return client.post_xml(f"/view/{name}/config.xml", config_xml)


def delete_view(client: JenkinsClient, name: str) -> None:
    """Delete an existing Jenkins view.

    Args:
        client: Authenticated Jenkins client.
        name: View name to delete.

    Raises:
        JenkinsAPIError: If the API request fails.
        JenkinsNotFoundError: If the view doesn't exist.
    """
    client.post_data(f"/view/{name}/doDelete", data="")
