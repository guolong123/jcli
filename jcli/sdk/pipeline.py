"""Jenkins Pipeline SDK functions.

Provides functions for querying Pipeline stages, step logs,
validating Jenkinsfiles, and checking pending input actions.
"""

from __future__ import annotations

from typing import Any

from jcli.sdk.client import JenkinsClient


def get_pipeline_stages(
    client: JenkinsClient,
    job_name: str,
    build_number: int | str,
) -> Any:
    """Get Pipeline stage information for a specific build.

    Uses the Blue Ocean wfapi describe endpoint to retrieve stage
    and step topology for declarative or scripted Pipelines.

    Args:
        client: Configured JenkinsClient instance.
        job_name: Job (Pipeline) name.
        build_number: Build number to query.

    Returns:
        Parsed JSON response containing stages, status, and duration info.

    Raises:
        JenkinsNotFoundError: If job or build doesn't exist.
        JenkinsAuthError: If authentication fails.
        JenkinsAPIError: For other API errors.
    """
    path = f"job/{job_name}/{build_number}/wfapi/describe"
    return client.get_json(path)


def get_pipeline_log(
    client: JenkinsClient,
    job_name: str,
    build_number: int | str,
    node_id: str | int,
) -> Any:
    """Get log output for a specific Pipeline step (node).

    Uses the Blue Ocean wfapi log endpoint to retrieve console
    log text for an individual flow node (stage or parallel branch).

    Args:
        client: Configured JenkinsClient instance.
        job_name: Job (Pipeline) name.
        build_number: Build number to query.
        node_id: Flow node ID (from stage/step info in describe).

    Returns:
        Parsed JSON response containing log text and metadata.

    Raises:
        JenkinsNotFoundError: If job, build, or node doesn't exist.
        JenkinsAuthError: If authentication fails.
        JenkinsAPIError: For other API errors.
    """
    path = f"job/{job_name}/{build_number}/execution/node/{node_id}/wfapi/log"
    return client.get_json(path)


def validate_jenkinsfile(
    client: JenkinsClient,
    content: str,
) -> Any:
    """Validate a Jenkinsfile (declarative Pipeline) against the Jenkins server.

    Sends the Jenkinsfile content to the pipeline-model-converter endpoint
    and returns the validation result.

    Args:
        client: Configured JenkinsClient instance.
        content: Jenkinsfile content as a string.

    Returns:
        Parsed JSON response with validation results (errors, warnings).

    Raises:
        JenkinsAuthError: If authentication fails.
        JenkinsConnectionError: If server is unreachable.
    """
    resp = client.post_data(
        "/pipeline-model-converter/validate",
        data={"jenkinsfile": content},
    )
    return resp.json()


def get_pending_input(
    client: JenkinsClient,
    job_name: str,
    build_number: int | str,
) -> Any:
    """Get pending input actions for a Pipeline build.

    Retrieves input steps that are waiting for user interaction
    (e.g., approval gate, parameter input).

    Args:
        client: Configured JenkinsClient instance.
        job_name: Job (Pipeline) name.
        build_number: Build number to query.

    Returns:
        Parsed JSON response containing pending input actions.

    Raises:
        JenkinsNotFoundError: If job or build doesn't exist.
        JenkinsAuthError: If authentication fails.
        JenkinsAPIError: For other API errors.
    """
    path = f"job/{job_name}/{build_number}/wfapi/pendingInputActions"
    return client.get_json(path)
