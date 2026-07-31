"""Jenkins method plugins: build trigger, replay, node create."""
from __future__ import annotations

import json
import urllib.parse
from typing import Any

from cliyard.plugin import register_method


def _job_path(job_name: str) -> str:
    """Convert job name to Jenkins URL path (folder/sub → /job/folder/job/sub)."""
    segments = job_name.split("/")
    return "/job/" + "/job/".join(segments)


def _parse_key_values(items: Any) -> dict[str, str]:
    """Parse a sequence of ``KEY=VALUE`` strings into a dict."""
    result: dict[str, str] = {}
    for item in items or ():
        if "=" in item:
            k, v = item.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def _queue_item_from_location(http_client: Any, location: str) -> dict[str, Any] | None:
    """Follow a Jenkins Location header to the queue-item JSON.

    Handles both absolute URLs (``http://host/queue/item/12/``) and
    relative paths (``/queue/item/12/``).  Returns ``None`` when the
    queue item cannot be fetched.
    """
    if not location:
        return None
    queue_path = urllib.parse.urlparse(location).path
    if queue_path.startswith(http_client.base_url):
        queue_path = queue_path[len(http_client.base_url):]
    if not queue_path.startswith("/"):
        queue_path = "/" + queue_path
    try:
        resp = http_client.request("GET", queue_path.rstrip("/") + "/api/json")
        return resp.json()
    except Exception:
        return None


@register_method("jenkins_build_trigger")
def jenkins_build_trigger(
    params: dict[str, Any], http_client: Any, config: dict[str, Any]
) -> dict[str, Any]:
    """Trigger a build with Location header following.

    POST /job/{job}/build or /buildWithParameters, follow Location to queue item.

    Args:
        params: Body params — ``job_name`` (str), ``params`` (list of
            ``KEY=VALUE`` strings).
        http_client: Configured HttpClient instance.
        config: Plugin configuration (unused).

    Returns:
        Dict with ``status``, ``url`` (queue item URL) and optionally
        ``queue_item`` (parsed queue-item JSON).
    """
    job_name = params.get("job_name", "")
    build_params = _parse_key_values(params.get("params"))

    path = _job_path(job_name)
    if build_params:
        url = f"{path}/buildWithParameters"
        resp = http_client.request("POST", url, query_params=build_params)
    else:
        url = f"{path}/build"
        resp = http_client.request("POST", url)

    location = resp.headers.get("Location", "")
    queue_item = _queue_item_from_location(http_client, location)
    if queue_item is not None:
        return {"status": "queued", "url": location, "queue_item": queue_item}
    return {"status": "queued", "url": location}


@register_method("jenkins_build_rebuild")
def jenkins_build_rebuild(
    params: dict[str, Any], http_client: Any, config: dict[str, Any]
) -> dict[str, Any]:
    """Rebuild a build: auto-fetch previous build parameters + ``--set`` override.

    Flow: GET previous parameters → merge ``--set`` overrides →
    POST buildWithParameters or /build.

    Args:
        params: Body params — ``job_name`` (str), ``build_number`` (int),
            ``set`` (list of ``KEY=VALUE`` overrides).
        http_client: Configured HttpClient instance.
        config: Plugin configuration (unused).

    Returns:
        Dict with ``status``, ``url`` (queue item URL) and ``parameters``
        (the merged parameter dict actually sent).
    """
    job_name = params.get("job_name", "")
    build_number = params.get("build_number", 0)
    set_overrides = params.get("set") or ()

    path = _job_path(job_name)

    # Step 1: Fetch previous build parameters
    build_params: dict[str, str] = {}
    try:
        resp = http_client.request(
            "GET",
            f"{path}/{build_number}/api/json",
            query_params={"tree": "actions[parameters[name,value]]"},
        )
        for action in resp.json().get("actions", []):
            for p in action.get("parameters", []):
                build_params[str(p["name"])] = p["value"]
    except Exception:
        pass  # Non-parameterized build

    # Step 2: Apply --set overrides
    build_params.update(_parse_key_values(set_overrides))

    # Step 3: Trigger build
    if build_params:
        resp = http_client.request(
            "POST", f"{path}/buildWithParameters", query_params=build_params
        )
    else:
        resp = http_client.request("POST", f"{path}/build")

    location = resp.headers.get("Location", "")
    return {"status": "queued", "url": location, "parameters": build_params}


@register_method("jenkins_build_replay")
def jenkins_build_replay(
    params: dict[str, Any], http_client: Any, config: dict[str, Any]
) -> dict[str, Any]:
    """Replay a build with a provided Jenkinsfile via the Jenkins Replay API.

    POST /job/{job}/{build}/replay/run with form data carrying the
    Jenkinsfile content (``_.mainScript``), a crumb, the ``Submit``
    button value and the serialized ``json`` form.  On success Jenkins
    responds with a 302 redirect (new build queued) or 200.

    Args:
        params: Body params — ``job_name`` (str), ``build_number`` (int),
            ``jenkinsfile`` (str, file content or path to read).
        http_client: Configured HttpClient instance.
        config: Plugin configuration (unused).

    Returns:
        Dict with ``status`` (``replayed``/``failed``), ``job`` and
        ``build``; on failure also ``code`` and ``detail``.
    """
    import os as _os

    job_name = params.get("job_name", "")
    build_number = params.get("build_number", 0)
    jenkinsfile = params.get("jenkinsfile", "")

    # ``type: file`` may arrive as a path string (plugin callbacks do not
    # pre-read file contents) — read it when it points at an existing file.
    if jenkinsfile and _os.path.isfile(jenkinsfile):
        with open(jenkinsfile, encoding="utf-8") as _f:
            jenkinsfile = _f.read()

    path = _job_path(job_name)

    crumb = http_client.default_headers.get("Jenkins-Crumb", "")
    if not crumb:
        try:
            resp = http_client.request("GET", "/crumbIssuer/api/json")
            crumb = resp.json().get("crumb", "")
        except Exception:
            crumb = ""

    # F12-verified Replay form (4 fields; missing ones cause 400/500).
    form_data = {
        "_.mainScript": jenkinsfile,
        "Submit": "运行",
        "Jenkins-Crumb": crumb,
        "json": json.dumps(
            {"mainScript": jenkinsfile, "": "", "Submit": "运行", "Jenkins-Crumb": crumb},
            ensure_ascii=False,
        ),
    }
    # Form-encoded POST — _session directly (HttpClient.request would JSON-encode).
    resp = http_client._session.post(
        f"{http_client.base_url}{path}/{build_number}/replay/run",
        data=form_data,
        headers={**http_client.default_headers, "Content-Type": "application/x-www-form-urlencoded"},
        timeout=getattr(http_client, "timeout", 30),
        allow_redirects=False,
    )
    if resp.status_code in (302, 200):
        return {"status": "replayed", "job": job_name, "build": build_number}
    return {"status": "failed", "code": resp.status_code, "detail": resp.text[:300]}


@register_method("jenkins_node_create")
def jenkins_node_create(
    params: dict[str, Any], http_client: Any, config: dict[str, Any]
) -> dict[str, Any]:
    """Create a Jenkins agent node via form-encoded POST.

    POST /computer/doCreateItem with form-encoded data (not JSON).

    Args:
        params: Body params — ``name`` (str), ``num_executors`` (int),
            ``remote_fs`` (str), ``labels`` (str), ``launch_method`` (str).
        http_client: Configured HttpClient instance.
        config: Plugin configuration (unused).

    Returns:
        Dict with ``status`` and ``name``.
    """
    name = params.get("name", "")
    num_executors = params.get("num_executors", 1)
    remote_fs = params.get("remote_fs", "/tmp")
    labels = params.get("labels", "")
    launch_method = params.get("launch_method", "hudson.slaves.JNLPLauncher")

    node_json = json.dumps({
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
    })

    # Form-encoded (not JSON) — use _session directly with merged default
    # headers so the Authorization / crumb chain still applies.
    form_data = (
        f"name={urllib.parse.quote(name)}"
        f"&type=hudson.slaves.DumbSlave"
        f"&json={urllib.parse.quote(node_json)}"
    )
    http_client._session.post(
        f"{http_client.base_url}/computer/doCreateItem",
        params={"name": name, "type": "hudson.slaves.DumbSlave"},
        data=form_data,
        headers={**http_client.default_headers, "Content-Type": "application/x-www-form-urlencoded"},
        timeout=http_client.timeout,
    )
    return {"status": "created", "name": name}
