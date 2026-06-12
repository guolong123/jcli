"""Jenkins Credential SDK.
 
Provides functions for managing Jenkins credentials via the REST API.
Default store is ``system``, default domain is ``_`` (global domain).
 
API reference:
  - List:   GET  /credentials/store/{store}/domain/{domain}/api/json
  - Get:    GET  /credentials/store/{store}/domain/_/credential/{id}/api/json
  - Create: POST /credentials/store/{store}/domain/{domain}/createCredentials
  - Update: POST /credentials/store/{store}/domain/_/credential/{id}/updateCredentials
  - Delete: POST /credentials/store/{store}/domain/{domain}/credential/{id}/doDelete
"""

from __future__ import annotations

from typing import Any

from jcli.sdk.client import JenkinsClient


DEFAULT_STORE = "system"
DEFAULT_DOMAIN = "_"


def _build_base_path(store: str, domain: str) -> str:
    """Build the base path for credential store/domain operations."""
    return f"/credentials/store/{store}/domain/{domain}"


def list_credentials(
    client: JenkinsClient,
    store: str = DEFAULT_STORE,
    domain: str = DEFAULT_DOMAIN,
    depth: int | None = None,
) -> Any:
    """List all credentials in a store/domain.

    Args:
        client: Jenkins API client.
        store: Credential store ID (default: ``system``).
        domain: Credential domain ID (default: ``_``).
        depth: Optional API depth parameter for nested expansion.

    Returns:
        Parsed JSON response from Jenkins.
    """
    path = f"{_build_base_path(store, domain)}/api/json"
    params: dict[str, Any] = {}
    if depth is not None:
        params["depth"] = str(depth)
    return client.get_json(path, params=params)


def get_credential(
    client: JenkinsClient,
    cred_id: str,
    store: str = DEFAULT_STORE,
) -> Any:
    """Get details of a single credential.

    Args:
        client: Jenkins API client.
        cred_id: Credential ID.
        store: Credential store ID (default: ``system``).

    Returns:
        Parsed JSON response containing credential details.
    """
    path = (
        f"{_build_base_path(store, DEFAULT_DOMAIN)}"
        f"/credential/{cred_id}/api/json"
    )
    return client.get_json(path)


def create_credential(
    client: JenkinsClient,
    xml_data: str | bytes,
    store: str = DEFAULT_STORE,
    domain: str = DEFAULT_DOMAIN,
) -> Any:
    """Create a new credential from XML config.

    The XML must follow the Jenkins credentials XStream format for the
    target credential type (e.g. ``UsernamePasswordCredentialsImpl``).

    Args:
        client: Jenkins API client.
        xml_data: Credential XML config (str or bytes).
        store: Credential store ID (default: ``system``).
        domain: Credential domain ID (default: ``_``).

    Returns:
        ``requests.Response`` from the POST request.
    """
    path = f"{_build_base_path(store, domain)}/createCredentials"
    return client.post_xml(path, xml_data)


def update_credential(
    client: JenkinsClient,
    cred_id: str,
    xml_data: str | bytes,
    store: str = DEFAULT_STORE,
) -> Any:
    """Update an existing credential.

    Args:
        client: Jenkins API client.
        cred_id: Credential ID to update.
        xml_data: New credential XML config.
        store: Credential store ID (default: ``system``).

    Returns:
        ``requests.Response`` from the POST request.
    """
    path = (
        f"{_build_base_path(store, DEFAULT_DOMAIN)}"
        f"/credential/{cred_id}/updateCredentials"
    )
    return client.post_xml(path, xml_data)


def delete_credential(
    client: JenkinsClient,
    cred_id: str,
    store: str = DEFAULT_STORE,
) -> Any:
    """Delete a credential.

    Args:
        client: Jenkins API client.
        cred_id: Credential ID to delete.
        store: Credential store ID (default: ``system``).

    Returns:
        ``requests.Response`` from the POST request.
    """
    path = (
        f"{_build_base_path(store, DEFAULT_DOMAIN)}"
        f"/credential/{cred_id}/doDelete"
    )
    return client.post_data(path, data={})
