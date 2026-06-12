"""Jenkins Build SDK — trigger, query, stop builds and manage queue."""

from __future__ import annotations

import time
import urllib.parse
from typing import Any

from jcli.sdk.client import JenkinsClient
from jcli.sdk.exceptions import JenkinsError


def _job_path(job_name: str) -> str:
    """Convert a job name to a Jenkins URL path segment.

    Handles nested jobs (folder/sub-job) by converting each slash-separated
    segment into ``/job/<segment>``.
    """
    segments = job_name.split("/")
    return "/job/" + "/job/".join(segments)


def trigger_build(
    client: JenkinsClient,
    job_name: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Trigger a new build for the given job.

    If *params* is provided the build is triggered with parameters via
    ``/buildWithParameters``, otherwise a plain ``/build`` is used.
    Jenkins returns a ``Location`` header pointing to the queued item.
    This function follows that redirect and parses the queue-item JSON.

    :returns: Queue item info as returned by Jenkins (dict).
    """
    path = _job_path(job_name)
    if params:
        url = f"{path}/buildWithParameters"
        resp = client.request("POST", url, params=params, allow_redirects=False)
    else:
        url = f"{path}/build"
        resp = client.request("POST", url, allow_redirects=False)

    # Jenkins responds with 201 Created or 302 Found and a Location header
    # pointing to the queue item.  Follow that URL to get the queue item JSON.
    location = resp.headers.get("Location")
    if location:
        queue_path = urllib.parse.urlparse(location).path
        # Strip the base URL prefix — client.get_json accepts an absolute path
        if queue_path.startswith(client.base_url):
            queue_path = queue_path[len(client.base_url) :]
        try:
            return client.get_json(queue_path + "api/json")
        except JenkinsError:
            pass

    # Fallback — return a minimal dict
    return {"status": "queued", "url": location or ""}


def get_build(
    client: JenkinsClient,
    job_name: str,
    number: int,
) -> dict[str, Any]:
    """Get details for a specific build.

    :returns: Build details as returned by the Jenkins API.
    """
    path = f"{_job_path(job_name)}/{number}"
    return client.get_json(f"{path}/api/json")


def get_builds(
    client: JenkinsClient,
    job_name: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """List recent builds for a job.

    :param limit: Maximum number of builds to return (applied client-side).
    :returns: List of build dicts (trimmed to *limit*).
    """
    path = _job_path(job_name)
    tree = f"builds[number,url,result,timestamp,duration,building]{f'{{{0},{limit - 1}}}' if limit > 0 else ''}"
    data = client.get_json(f"{path}/api/json", tree=tree)
    builds: list[dict[str, Any]] = data.get("builds", [])
    return builds[:limit]


def get_build_log(
    client: JenkinsClient,
    job_name: str,
    number: int,
    start: int = 0,
) -> str:
    """Retrieve the console log for a build.

    :param start: Byte offset to start reading from (useful for polling).
    :returns: Console log text.
    """
    path = f"{_job_path(job_name)}/{number}/consoleText"
    resp = client.request("GET", path)
    text = resp.text
    if start > 0:
        return text[start:]
    return text


def stop_build(
    client: JenkinsClient,
    job_name: str,
    number: int,
) -> dict[str, Any]:
    """Stop (abort) a running build.

    :returns: Empty dict on success.
    """
    path = f"{_job_path(job_name)}/{number}"
    client.request("POST", f"{path}/stop")
    return {}


def get_queue(client: JenkinsClient) -> list[dict[str, Any]]:
    """Return all items currently in the Jenkins build queue.

    :returns: List of queue item dicts.
    """
    data = client.get_json("/queue/api/json")
    return data.get("items", [])


def cancel_queue_item(
    client: JenkinsClient,
    queue_id: int,
) -> dict[str, Any]:
    """Cancel a queued item.

    :param queue_id: Numeric queue item ID.
    :returns: Empty dict on success.
    """
    client.request("POST", "/queue/cancelItem", params={"id": queue_id})
    return {}


def get_build_artifacts(
    client: JenkinsClient,
    job_name: str,
    build_number: int | str,
) -> Any:
    """Get build artifacts.

    Lists artifacts produced by a build.
    """
    path = _job_path(job_name) + f"/{build_number}/api/json"
    return client.get_json(path, tree="artifacts[fileName,relativePath]")


def wait_for_build(
    client: JenkinsClient,
    job_name: str,
    number: int,
    timeout: int = 600,
    poll_interval: int = 2,
) -> dict[str, Any]:
    """Poll until a build completes or *timeout* is reached.

    :param timeout: Maximum seconds to wait.
    :param poll_interval: Seconds between status checks.
    :returns: Final build dict.
    :raises TimeoutError: if the build does not finish within *timeout*.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        build = get_build(client, job_name, number)
        if not build.get("building", False):
            return build
        time.sleep(poll_interval)
    raise TimeoutError(
        f"Build {job_name}#{number} did not complete within {timeout}s"
    )
