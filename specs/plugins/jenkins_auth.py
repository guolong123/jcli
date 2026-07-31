"""Jenkins auth steps: Basic Auth + Crumb (CSRF)."""
import base64
import os

import requests

from cliyard.plugin import register_auth_step


def _config_path() -> str:
    """Resolve the jcli config file path at call time.

    Prefers ``jcli.sdk.config.DEFAULT_CONFIG_FILE`` (so tests can point it
    elsewhere via monkeypatch) and falls back to ``~/.jcli/config.yaml``
    when the SDK is not importable.
    """
    try:
        from jcli.sdk.config import DEFAULT_CONFIG_FILE

        return str(DEFAULT_CONFIG_FILE)
    except Exception:
        return os.path.expanduser("~/.jcli/config.yaml")


def _load_profile():
    import yaml
    config_path = _config_path()
    if not os.path.exists(config_path):
        raise RuntimeError(f"config not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    name = os.environ.get("JCLI_PROFILE") or cfg.get("active_profile", "default")
    profile = dict(cfg.get("profiles", {}).get(name, {}))
    for env_key, field in (("JCLI_URL", "url"), ("JCLI_USERNAME", "username"), ("JCLI_API_TOKEN", "api_token")):
        if os.environ.get(env_key):
            profile[field] = os.environ[env_key]
    return profile


@register_auth_step("jenkins_basic")
class JenkinsBasicAuth:
    """Set Basic Auth header from ~/.jcli/config.yaml profile."""

    def execute(self, auth_state, config, http_client):
        profile = _load_profile()
        username = profile.get("username", "")
        token = profile.get("api_token", "")
        if not username or not token:
            raise RuntimeError("missing username/api_token in profile")
        raw = f"{username}:{token}".encode()
        http_client.default_headers["Authorization"] = "Basic " + base64.b64encode(raw).decode()
        auth_state["username"] = username
        return {"username": username}


@register_auth_step("jenkins_crumb")
class JenkinsCrumb:
    """Fetch Jenkins crumb and inject as header. Tolerate 404 (CSRF disabled)."""

    def execute(self, auth_state, config, http_client):
        url = f"{http_client.base_url}/crumbIssuer/api/json"
        try:
            resp = http_client._session.get(url, headers=http_client.default_headers, timeout=10)
        except requests.RequestException:
            return {}
        if resp.status_code == 404:
            return {}  # CSRF disabled
        if resp.status_code != 200:
            raise RuntimeError(f"crumb fetch failed: {resp.status_code}")
        data = resp.json()
        field = data.get("crumbRequestField")
        value = data.get("crumb")
        if field and value:
            http_client.default_headers[field] = value
        return {"crumb": value}
