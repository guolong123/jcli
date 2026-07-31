"""Tests for jcli.sdk.client — JenkinsClient HTTP client.

jcli 2.0 mapping (v1 → v2):
- v1 ``jcli.sdk.client.JenkinsClient`` is retained as the SDK compatibility
  layer (HTTP + auth + crumb + retry) and is still exercised here.
- The v2 CLI does NOT use it: requests go through cliyard's ``HttpClient``
  with the auth chain defined in ``specs/_auth.yaml`` and implemented by
  ``specs/plugins/jenkins_auth.py`` (basic auth + crumb).  This file keeps
  covering the SDK-level behaviors (crumb lazily fetched/cached, error
  mapping, retry on 503/504) that the v2 auth plugin relies on.
"""

from __future__ import annotations

import pytest
import responses
from requests.exceptions import ConnectionError as ReqConnectionError

from jcli.sdk.client import JenkinsClient
from jcli.sdk.exceptions import (
    JenkinsAPIError,
    JenkinsAuthError,
    JenkinsConnectionError,
    JenkinsCrumbError,
    JenkinsNotFoundError,
)

BASE_URL = "http://jenkins.example.com"
CRUMB_URL = f"{BASE_URL}/crumbIssuer/api/json"
CRUMB_RESPONSE = {
    "crumb": "abc123",
    "crumbRequestField": "Jenkins-Crumb",
}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _register_crumb(responses_mock: responses.RequestsMock) -> None:
    """Register a successful crumb endpoint."""
    responses_mock.add(
        responses.GET,
        CRUMB_URL,
        json=CRUMB_RESPONSE,
        status=200,
    )


# ==================================================================
# Client initialization
# ==================================================================


class TestClientInit:
    def test_basic_init(self) -> None:
        client = JenkinsClient("http://localhost:8080")
        assert client.base_url == "http://localhost:8080"
        assert client.session.auth is None

    def test_trailing_slash_stripped(self) -> None:
        client = JenkinsClient("http://localhost:8080/")
        assert client.base_url == "http://localhost:8080"

    def test_auth_set_when_credentials_provided(self) -> None:
        client = JenkinsClient(BASE_URL, username="admin", token="tok")
        assert client.session.auth == ("admin", "tok")

    def test_auth_not_set_without_credentials(self) -> None:
        client = JenkinsClient(BASE_URL)
        assert client.session.auth is None

    def test_partial_credentials_no_auth(self) -> None:
        client = JenkinsClient(BASE_URL, username="admin")
        assert client.session.auth is None


# ==================================================================
# URL construction
# ==================================================================


class TestUrlConstruction:
    def test_path_stripped(self) -> None:
        client = JenkinsClient(BASE_URL)
        assert client._url("/api/json") == f"{BASE_URL}/api/json"

    def test_path_no_leading_slash(self) -> None:
        client = JenkinsClient(BASE_URL)
        assert client._url("api/json") == f"{BASE_URL}/api/json"

    def test_nested_path(self) -> None:
        client = JenkinsClient(BASE_URL)
        assert client._url("job/test-job/1/") == f"{BASE_URL}/job/test-job/1/"


# ==================================================================
# Crumb handling
# ==================================================================


class TestCrumbHandling:
    @responses.activate
    def test_crumb_fetched_lazily_on_post(self) -> None:
        _register_crumb(responses)
        responses.add(responses.POST, f"{BASE_URL}/test", json={}, status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        client.post_data("/test", data={})

        assert responses.calls[0].request.url == CRUMB_URL
        assert responses.calls[1].request.headers.get("Jenkins-Crumb") == "abc123"

    @responses.activate
    def test_crumb_not_fetched_on_get(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/api/json", json={}, status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        client.get_json("/api/json")

        assert len(responses.calls) == 1
        assert responses.calls[0].request.url != CRUMB_URL

    @responses.activate
    def test_crumb_cached_after_first_post(self) -> None:
        _register_crumb(responses)
        responses.add(responses.POST, f"{BASE_URL}/test1", json={}, status=200)
        responses.add(responses.POST, f"{BASE_URL}/test2", json={}, status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        client.post_data("/test1", data={})
        client.post_data("/test2", data={})

        # Crumb fetched only once
        crumb_calls = [
            c for c in responses.calls if c.request.url == CRUMB_URL
        ]
        assert len(crumb_calls) == 1

    @responses.activate
    def test_crumb_404_ignored(self) -> None:
        """Crumb issuer disabled (404) is not an error."""
        responses.add(responses.GET, CRUMB_URL, status=404)
        responses.add(responses.POST, f"{BASE_URL}/test", json={}, status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        client.post_data("/test", data={})
        # Should not raise

    @responses.activate
    def test_crumb_fetch_failure_raises(self) -> None:
        responses.add(responses.GET, CRUMB_URL, status=500)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        with pytest.raises(JenkinsCrumbError, match="status 500"):
            client.post_data("/test", data={})

    @responses.activate
    def test_crumb_invalid_json(self) -> None:
        responses.add(responses.GET, CRUMB_URL, body="not-json", status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        with pytest.raises(JenkinsCrumbError, match="not valid JSON"):
            client.post_data("/test", data={})

    @responses.activate
    def test_crumb_missing_fields(self) -> None:
        responses.add(responses.GET, CRUMB_URL, json={"crumb": "x"}, status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        with pytest.raises(JenkinsCrumbError, match="missing header"):
            client.post_data("/test", data={})

    @responses.activate
    def test_crumb_connection_error(self) -> None:
        responses.add(
            responses.GET,
            CRUMB_URL,
            body=ReqConnectionError("refused"),
        )

        client = JenkinsClient(BASE_URL, username="a", token="t")
        with pytest.raises(JenkinsCrumbError, match="Failed to connect"):
            client.post_data("/test", data={})

    @responses.activate
    def test_crumb_delete_also_fetches(self) -> None:
        _register_crumb(responses)
        responses.add(responses.DELETE, f"{BASE_URL}/test", status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        client.request("DELETE", "/test")

        assert responses.calls[0].request.url == CRUMB_URL


# ==================================================================
# Error mapping
# ==================================================================


class TestErrorMapping:
    @responses.activate
    def test_401_raises_auth_error(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/api/json", status=401)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        with pytest.raises(JenkinsAuthError):
            client.get_json("/api/json")

    @responses.activate
    def test_404_raises_not_found(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/api/json", status=404)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        with pytest.raises(JenkinsNotFoundError):
            client.get_json("/api/json")

    @responses.activate
    def test_403_raises_api_error(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/api/json", status=403)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        with pytest.raises(JenkinsAPIError) as exc_info:
            client.get_json("/api/json")
        assert exc_info.value.status_code == 403

    @responses.activate
    def test_500_raises_api_error(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/api/json", status=500)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        with pytest.raises(JenkinsAPIError) as exc_info:
            client.get_json("/api/json")
        assert exc_info.value.status_code == 500

    @responses.activate
    def test_200_no_error(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/api/json", json={"ok": True}, status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        result = client.get_json("/api/json")
        assert result == {"ok": True}


# ==================================================================
# Connection errors
# ==================================================================


class TestConnectionErrors:
    def test_connection_error_maps(self) -> None:
        client = JenkinsClient("http://unreachable:9999", username="a", token="t")
        with pytest.raises(JenkinsConnectionError, match="Connection failed"):
            client.get_json("/api/json")

    @responses.activate
    def test_timeout_maps(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json",
            body=ReqConnectionError("Simulated timeout"),
        )
        client = JenkinsClient(BASE_URL, username="a", token="t")
        with pytest.raises(JenkinsConnectionError, match="Connection failed"):
            client.get_json("/api/json")

    def test_dns_error_maps(self) -> None:
        client = JenkinsClient("http://does-not-exist.invalid", username="a", token="t")
        with pytest.raises(JenkinsConnectionError):
            client.get_json("/api/json")


# ==================================================================
# Retry on 503/504
# ==================================================================


class TestRetry:
    @responses.activate
    def test_503_retries_once_then_success(self) -> None:
        _register_crumb(responses)
        responses.add(responses.POST, f"{BASE_URL}/test", status=503)
        responses.add(responses.POST, f"{BASE_URL}/test", json={}, status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        resp = client.post_data("/test", data={})
        assert resp.status_code == 200
        assert len(responses.calls) == 3  # crumb + 503 + success

    @responses.activate
    def test_504_retries_once(self) -> None:
        _register_crumb(responses)
        responses.add(responses.POST, f"{BASE_URL}/test", status=504)
        responses.add(responses.POST, f"{BASE_URL}/test", json={}, status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        resp = client.post_data("/test", data={})
        assert resp.status_code == 200

    @responses.activate
    def test_503_exhausts_retries(self) -> None:
        _register_crumb(responses)
        # Two 503s: first attempt + 1 retry
        responses.add(responses.POST, f"{BASE_URL}/test", status=503)
        responses.add(responses.POST, f"{BASE_URL}/test", status=503)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        with pytest.raises(JenkinsAPIError) as exc_info:
            client.post_data("/test", data={})
        assert exc_info.value.status_code == 503

    @responses.activate
    def test_no_retry_on_400(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/api/json", status=400)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        with pytest.raises(JenkinsAPIError):
            client.get_json("/api/json")
        assert len(responses.calls) == 1

    @responses.activate
    def test_retry_zero_disables(self) -> None:
        responses.add(responses.POST, f"{BASE_URL}/test", status=503)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        # Bypass crumb for simplicity
        client._crumb_header = "X-Crumb"
        client._crumb_value = "dummy"
        with pytest.raises(JenkinsAPIError):
            client.request("POST", "/test", retries=0)
        assert len(responses.calls) == 1


# ==================================================================
# get_json
# ==================================================================


class TestGetJson:
    @responses.activate
    def test_get_json_simple(self) -> None:
        responses.add(
            responses.GET, f"{BASE_URL}/api/json", json={"jobs": []}, status=200
        )
        client = JenkinsClient(BASE_URL)
        assert client.get_json("/api/json") == {"jobs": []}

    @responses.activate
    def test_get_json_with_params(self) -> None:
        responses.add(
            responses.GET, f"{BASE_URL}/api/json", json={}, status=200
        )
        client = JenkinsClient(BASE_URL)
        client.get_json("/api/json", params={"depth": 1})
        assert "depth=1" in responses.calls[0].request.url

    @responses.activate
    def test_get_json_with_tree(self) -> None:
        responses.add(
            responses.GET, f"{BASE_URL}/api/json", json={}, status=200
        )
        client = JenkinsClient(BASE_URL)
        client.get_json("/api/json", tree="jobs[name,url]")
        assert "tree=jobs%5Bname%2Curl%5D" in responses.calls[0].request.url

    @responses.activate
    def test_get_json_tree_merges_with_params(self) -> None:
        responses.add(
            responses.GET, f"{BASE_URL}/api/json", json={}, status=200
        )
        client = JenkinsClient(BASE_URL)
        client.get_json("/api/json", params={"depth": 2}, tree="jobs[name]")
        url = responses.calls[0].request.url
        assert "depth=2" in url
        assert "tree=jobs%5Bname%5D" in url

    @responses.activate
    def test_get_json_list_response(self) -> None:
        data = [{"name": "a"}, {"name": "b"}]
        responses.add(responses.GET, f"{BASE_URL}/api/json", json=data, status=200)
        client = JenkinsClient(BASE_URL)
        assert client.get_json("/api/json") == data


# ==================================================================
# post_xml
# ==================================================================


class TestPostXml:
    @responses.activate
    def test_post_xml_string(self) -> None:
        _register_crumb(responses)
        responses.add(responses.POST, f"{BASE_URL}/createItem", json={}, status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        resp = client.post_xml("/createItem", "<project/>")

        assert resp.status_code == 200
        assert responses.calls[1].request.headers["Content-Type"] == "application/xml"
        assert responses.calls[1].request.body == b"<project/>"

    @responses.activate
    def test_post_xml_bytes(self) -> None:
        _register_crumb(responses)
        responses.add(responses.POST, f"{BASE_URL}/createItem", json={}, status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        resp = client.post_xml("/createItem", b"<project/>")

        assert resp.status_code == 200
        assert responses.calls[1].request.body == b"<project/>"

    @responses.activate
    def test_post_xml_unicode(self) -> None:
        _register_crumb(responses)
        responses.add(responses.POST, f"{BASE_URL}/createItem", json={}, status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        resp = client.post_xml("/createItem", "<project><name>测试</name></project>")

        assert resp.status_code == 200
        body = responses.calls[1].request.body
        assert "测试".encode("utf-8") in body


# ==================================================================
# post_data
# ==================================================================


class TestPostData:
    @responses.activate
    def test_post_data_dict(self) -> None:
        _register_crumb(responses)
        responses.add(responses.POST, f"{BASE_URL}/submit", json={}, status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        client.post_data("/submit", data={"key": "value"})

        ct = responses.calls[1].request.headers["Content-Type"]
        assert "application/x-www-form-urlencoded" in ct

    @responses.activate
    def test_post_data_custom_content_type(self) -> None:
        _register_crumb(responses)
        responses.add(responses.POST, f"{BASE_URL}/submit", json={}, status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        client.post_data(
            "/submit",
            data='{"a":1}',
            content_type="application/json",
        )

        ct = responses.calls[1].request.headers["Content-Type"]
        assert ct == "application/json"
        assert responses.calls[1].request.body == '{"a":1}'


# ==================================================================
# request method
# ==================================================================


class TestRequestMethod:
    @responses.activate
    def test_get_method(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/api/json", json={}, status=200)

        client = JenkinsClient(BASE_URL)
        resp = client.request("GET", "/api/json")
        assert resp.status_code == 200

    @responses.activate
    def test_put_method(self) -> None:
        _register_crumb(responses)
        responses.add(responses.PUT, f"{BASE_URL}/update", json={}, status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        resp = client.request("PUT", "/update", json={"key": "val"})
        assert resp.status_code == 200

    @responses.activate
    def test_delete_method(self) -> None:
        _register_crumb(responses)
        responses.add(responses.DELETE, f"{BASE_URL}/remove", status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        resp = client.request("DELETE", "/remove")
        assert resp.status_code == 200

    @responses.activate
    def test_custom_headers(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/api/json", json={}, status=200)

        client = JenkinsClient(BASE_URL)
        client.request("GET", "/api/json", headers={"X-Custom": "yes"})
        assert responses.calls[0].request.headers["X-Custom"] == "yes"

    @responses.activate
    def test_timeout_parameter(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/api/json", json={}, status=200)

        client = JenkinsClient(BASE_URL)
        client.request("GET", "/api/json", timeout=60)
        assert responses.calls[0].request.url == f"{BASE_URL}/api/json"


# ==================================================================
# Integration / edge cases
# ==================================================================


class TestEdgeCases:
    def test_no_auth_client_still_works(self) -> None:
        client = JenkinsClient(BASE_URL)
        assert client.base_url == BASE_URL
        assert client.session.auth is None

    @responses.activate
    def test_crumb_not_double_fetched(self) -> None:
        """Ensure crumb is fetched exactly once across multiple POSTs."""
        _register_crumb(responses)
        for i in range(5):
            responses.add(
                responses.POST, f"{BASE_URL}/test{i}", json={}, status=200
            )

        client = JenkinsClient(BASE_URL, username="a", token="t")
        for i in range(5):
            client.post_data(f"/test{i}", data={})

        crumb_calls = [
            c for c in responses.calls if "crumbIssuer" in c.request.url
        ]
        assert len(crumb_calls) == 1

    @responses.activate
    def test_post_always_includes_crumb(self) -> None:
        _register_crumb(responses)
        responses.add(responses.POST, f"{BASE_URL}/test", json={}, status=200)

        client = JenkinsClient(BASE_URL, username="a", token="t")
        client.post_data("/test", data={})

        post_request = responses.calls[1].request
        assert "Jenkins-Crumb" in post_request.headers
