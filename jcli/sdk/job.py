"""Jenkins Job SDK — CRUD and lifecycle operations for Jenkins jobs."""

from __future__ import annotations

from typing import Any

from jcli.sdk.client import JenkinsClient


def list_jobs(client: JenkinsClient, depth: int = 0) -> list[dict[str, Any]]:
    """List all jobs with name, url, and color.

    Args:
        client: Authenticated JenkinsClient instance.
        depth: Recursion depth for folder jobs (0 = top-level only).

    Returns:
        List of job dicts with keys: name, url, color.
    """
    data = client.get_json("/api/json", tree="jobs[name,url,color]")
    return data.get("jobs", [])


def get_job(client: JenkinsClient, name: str) -> dict[str, Any]:
    """Get full details for a specific job.

    Args:
        client: Authenticated JenkinsClient instance.
        name: Job name (URL-encoding is handled by the client).

    Returns:
        Job details dict as returned by the Jenkins REST API.

    Raises:
        JenkinsNotFoundError: If the job does not exist.
    """
    return client.get_json(f"/job/{name}/api/json")


def create_job(client: JenkinsClient, name: str, config_xml: str) -> None:
    """Create a new job from an XML configuration string.

    Args:
        client: Authenticated JenkinsClient instance.
        name: Name for the new job.
        config_xml: Jenkins job config XML as a string.

    Raises:
        JenkinsAPIError: On creation failure (e.g. duplicate name, bad XML).
    """
    client.post_xml(f"/createItem?name={name}", config_xml)


def delete_job(client: JenkinsClient, name: str) -> None:
    """Delete a job.

    Args:
        client: Authenticated JenkinsClient instance.
        name: Name of the job to delete.

    Raises:
        JenkinsNotFoundError: If the job does not exist.
    """
    client.post_data(f"/job/{name}/doDelete", data={})


def copy_job(client: JenkinsClient, from_name: str, new_name: str) -> None:
    """Copy an existing job to a new name.

    Args:
        client: Authenticated JenkinsClient instance.
        from_name: Source job name.
        new_name: Name for the copied job.

    Raises:
        JenkinsNotFoundError: If the source job does not exist.
    """
    client.post_data(
        "/createItem",
        data={"name": new_name, "mode": "copy", "from": from_name},
    )


def rename_job(
    client: "JenkinsClient",
    old_name: str,
    new_name: str,
) -> Any:
    """Rename a job.

    Args:
        client: Jenkins API client.
        old_name: Current job name.
        new_name: New job name.

    Returns:
        Response from Jenkins (redirect on success).

    Raises:
        JenkinsNotFoundError: If the job does not exist.
    """
    path = f"/job/{old_name}/doRename"
    return client.request("POST", path, params={"newName": new_name})


def enable_job(client: JenkinsClient, name: str) -> None:
    """Enable a disabled job.

    Args:
        client: Authenticated JenkinsClient instance.
        name: Name of the job to enable.

    Raises:
        JenkinsNotFoundError: If the job does not exist.
    """
    client.post_data(f"/job/{name}/enable", data={})


def disable_job(client: JenkinsClient, name: str) -> None:
    """Disable a job.

    Args:
        client: Authenticated JenkinsClient instance.
        name: Name of the job to disable.

    Raises:
        JenkinsNotFoundError: If the job does not exist.
    """
    client.post_data(f"/job/{name}/disable", data={})


def update_job_config(
    client: JenkinsClient,
    name: str,
    config_xml: str,
) -> Any:
    """Update a job's configuration.

    Args:
        client: Jenkins API client.
        name: Job name.
        config_xml: New XML configuration.

    Returns:
        Response from Jenkins.
    """
    return client.post_xml(f"/job/{name}/config.xml", config_xml)


def get_job_config(client: JenkinsClient, name: str) -> str:
    """Retrieve the XML configuration for a job.

    Args:
        client: Authenticated JenkinsClient instance.
        name: Name of the job.

    Returns:
        Job configuration as an XML string.

    Raises:
        JenkinsNotFoundError: If the job does not exist.
    """
    resp = client.request("GET", f"/job/{name}/config.xml")
    return resp.text


def create_folder(client: JenkinsClient, name: str) -> Any:
    """Create a Jenkins folder.

    Args:
        client: Jenkins API client.
        name: Folder name.

    Returns:
        Response from Jenkins.
    """
    path = f"/createItem?name={name}&mode=com.cloudbees.hudson.plugins.folder.Folder"
    return client.request("POST", path)


def delete_folder(client: JenkinsClient, name: str) -> Any:
    """Delete a Jenkins folder and all its contents.

    Args:
        client: Jenkins API client.
        name: Folder name.

    Returns:
        Response from Jenkins.
    """
    return client.request("POST", f"/job/{name}/doDelete")
