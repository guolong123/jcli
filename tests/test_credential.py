"""Unit tests for jcli.sdk.credential — SDK and CLI."""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch

import pytest
import responses
from click.testing import CliRunner

from jcli.sdk.client import JenkinsClient
from jcli.sdk.credential import (
    DEFAULT_DOMAIN,
    DEFAULT_STORE,
    create_credential,
    delete_credential,
    get_credential,
    list_credentials,
    update_credential,
)
from jcli.sdk.exceptions import JenkinsAPIError, JenkinsNotFoundError

BASE_URL = "http://jenkins.example.com"

SAMPLE_CRED_ID = "my-cred-id"
SAMPLE_STORE = "system"
SAMPLE_DOMAIN = "_"

# Sample response from GET /credentials/store/system/domain/_/api/json
SAMPLE_LIST_RESPONSE = {
    "class": "com.cloudbees.plugins.credentials.CredentialsStoreAction$CredentialsWrapper",
    "credentials": [
        {
            "id": "github-token",
            "typeName": "Secret text",
            "description": "GitHub API token",
            "fingerprint": None,
            "displayName": "github-token",
        },
        {
            "id": "deploy-key",
            "typeName": "SSH Username with private key",
            "description": "Deployment SSH key",
            "fingerprint": None,
            "displayName": "deploy-key",
        },
    ],
}

# Sample response from GET .../credential/{id}/api/json
SAMPLE_GET_RESPONSE = {
    "id": "github-token",
    "typeName": "Secret text",
    "description": "GitHub API token",
    "displayName": "github-token",
    "scope": "GLOBAL",
}

# Sample XML for creating a credential
SAMPLE_XML = """<com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>
  <scope>GLOBAL</scope>
  <id>my-cred-id</id>
  <description>My credential</description>
  <username>admin</username>
  <password>secret</password>
</com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>"""


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _url(path: str) -> str:
    return f"{BASE_URL}{path}"


def _list_url(store: str = SAMPLE_STORE, domain: str = SAMPLE_DOMAIN) -> str:
    return _url(f"/credentials/store/{store}/domain/{domain}/api/json")


def _get_url(cred_id: str, store: str = SAMPLE_STORE) -> str:
    return _url(
        f"/credentials/store/{store}/domain/{DEFAULT_DOMAIN}"
        f"/credential/{cred_id}/api/json"
    )


def _create_url(store: str = SAMPLE_STORE, domain: str = SAMPLE_DOMAIN) -> str:
    return _url(
        f"/credentials/store/{store}/domain/{domain}/createCredentials"
    )


def _delete_url(cred_id: str, store: str = SAMPLE_STORE) -> str:
    return _url(
        f"/credentials/store/{store}/domain/{DEFAULT_DOMAIN}"
        f"/credential/{cred_id}/doDelete"
    )


def _update_url(cred_id: str, store: str = SAMPLE_STORE) -> str:
    return _url(
        f"/credentials/store/{store}/domain/{DEFAULT_DOMAIN}"
        f"/credential/{cred_id}/updateCredentials"
    )


def _register_crumb(responses_mock: responses.RequestsMock) -> None:
    responses_mock.add(
        responses.GET,
        f"{BASE_URL}/crumbIssuer/api/json",
        json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
        status=200,
    )


@pytest.fixture
def client() -> JenkinsClient:
    """Return a JenkinsClient with auth for mutating requests."""
    return JenkinsClient(
        base_url=BASE_URL,
        username="admin",
        token="fake-token",
    )


# ==================================================================
# list_credentials
# ==================================================================


class TestListCredentials:
    @responses.activate
    def test_list_returns_credentials(self, client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _list_url(),
            json=SAMPLE_LIST_RESPONSE,
            status=200,
        )
        result = list_credentials(client)
        assert result == SAMPLE_LIST_RESPONSE
        assert len(result["credentials"]) == 2

    @responses.activate
    def test_list_with_custom_store(self, client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _list_url(store="folder-store"),
            json={"credentials": []},
            status=200,
        )
        result = list_credentials(client, store="folder-store")
        assert result == {"credentials": []}

    @responses.activate
    def test_list_with_custom_domain(self, client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _list_url(domain="github.com"),
            json=SAMPLE_LIST_RESPONSE,
            status=200,
        )
        result = list_credentials(client, domain="github.com")
        assert result == SAMPLE_LIST_RESPONSE

    @responses.activate
    def test_list_defaults(self, client: JenkinsClient) -> None:
        """Verify defaults match expected Jenkins API behavior."""
        responses.add(
            responses.GET,
            _list_url(store=DEFAULT_STORE, domain=DEFAULT_DOMAIN),
            json=SAMPLE_LIST_RESPONSE,
            status=200,
        )
        list_credentials(client)
        req_url = responses.calls[0].request.url
        assert f"/store/{DEFAULT_STORE}/domain/{DEFAULT_DOMAIN}" in req_url

    @responses.activate
    def test_list_empty_credentials(self, client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _list_url(),
            json={"credentials": []},
            status=200,
        )
        result = list_credentials(client)
        assert result["credentials"] == []

    @responses.activate
    def test_list_not_found(self, client: JenkinsClient) -> None:
        responses.add(responses.GET, _list_url(store="missing"), status=404)
        with pytest.raises(JenkinsNotFoundError):
            list_credentials(client, store="missing")


# ==================================================================
# get_credential
# ==================================================================


class TestGetCredential:
    @responses.activate
    def test_get_returns_details(self, client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _get_url(SAMPLE_CRED_ID),
            json=SAMPLE_GET_RESPONSE,
            status=200,
        )
        result = get_credential(client, SAMPLE_CRED_ID)
        assert result == SAMPLE_GET_RESPONSE
        assert result["id"] == "github-token"

    @responses.activate
    def test_get_with_custom_store(self, client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _get_url("folder-cred", store="folder-store"),
            json={"id": "folder-cred", "typeName": "Secret text"},
            status=200,
        )
        result = get_credential(client, "folder-cred", store="folder-store")
        assert result["id"] == "folder-cred"

    @responses.activate
    def test_get_default_store(self, client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _get_url("test-cred", store=DEFAULT_STORE),
            json=SAMPLE_GET_RESPONSE,
            status=200,
        )
        get_credential(client, "test-cred")
        req_url = responses.calls[0].request.url
        assert f"/store/{DEFAULT_STORE}/domain/{DEFAULT_DOMAIN}" in req_url
        assert "/credential/test-cred/api/json" in req_url

    @responses.activate
    def test_get_not_found(self, client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _get_url("no-such-cred"),
            status=404,
        )
        with pytest.raises(JenkinsNotFoundError):
            get_credential(client, "no-such-cred")


# ==================================================================
# create_credential
# ==================================================================


class TestCreateCredential:
    @responses.activate
    def test_create_with_xml_string(self, client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(responses.POST, _create_url(), status=200)

        resp = create_credential(client, SAMPLE_XML)
        assert resp.status_code == 200
        post_call = responses.calls[1]
        assert post_call.request.body == SAMPLE_XML.encode("utf-8")
        assert post_call.request.headers["Content-Type"] == "application/xml"

    @responses.activate
    def test_create_with_xml_bytes(self, client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(responses.POST, _create_url(), status=200)

        xml_bytes = SAMPLE_XML.encode("utf-8")
        resp = create_credential(client, xml_bytes)
        assert resp.status_code == 200
        assert responses.calls[1].request.body == xml_bytes

    @responses.activate
    def test_create_custom_store_domain(self, client: JenkinsClient) -> None:
        _register_crumb(responses)
        url = _create_url(store="folder-store", domain="github.com")
        responses.add(responses.POST, url, status=200)

        resp = create_credential(
            client, SAMPLE_XML, store="folder-store", domain="github.com"
        )
        assert resp.status_code == 200
        assert "/store/folder-store/domain/github.com/createCredentials" in (
            responses.calls[1].request.url
        )

    @responses.activate
    def test_create_defaults(self, client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            _create_url(store=DEFAULT_STORE, domain=DEFAULT_DOMAIN),
            status=200,
        )
        create_credential(client, SAMPLE_XML)
        req_url = responses.calls[1].request.url
        assert f"/store/{DEFAULT_STORE}/domain/{DEFAULT_DOMAIN}/createCredentials" in req_url

    @responses.activate
    def test_create_returns_error(self, client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(responses.POST, _create_url(), status=400, body="Invalid XML")

        with pytest.raises(JenkinsAPIError, match="400"):
            create_credential(client, "<bad-xml>")


# ==================================================================
# update_credential
# ==================================================================


class TestUpdateCredential:
    @responses.activate
    def test_update_with_xml_string(self, client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(responses.POST, _update_url(SAMPLE_CRED_ID), status=200)

        resp = update_credential(client, SAMPLE_CRED_ID, SAMPLE_XML)
        assert resp.status_code == 200
        post_call = responses.calls[1]
        assert post_call.request.body == SAMPLE_XML.encode("utf-8")
        assert post_call.request.headers["Content-Type"] == "application/xml"

    @responses.activate
    def test_update_with_xml_bytes(self, client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(responses.POST, _update_url(SAMPLE_CRED_ID), status=200)

        xml_bytes = SAMPLE_XML.encode("utf-8")
        resp = update_credential(client, SAMPLE_CRED_ID, xml_bytes)
        assert resp.status_code == 200
        assert responses.calls[1].request.body == xml_bytes

    @responses.activate
    def test_update_custom_store(self, client: JenkinsClient) -> None:
        _register_crumb(responses)
        url = _update_url("folder-cred", store="folder-store")
        responses.add(responses.POST, url, status=200)

        resp = update_credential(
            client, "folder-cred", SAMPLE_XML, store="folder-store"
        )
        assert resp.status_code == 200
        assert "/store/folder-store/domain/_/credential/folder-cred/updateCredentials" in (
            responses.calls[1].request.url
        )

    @responses.activate
    def test_update_defaults(self, client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            _update_url("test-cred", store=DEFAULT_STORE),
            status=200,
        )
        update_credential(client, "test-cred", SAMPLE_XML)
        req_url = responses.calls[1].request.url
        assert f"/store/{DEFAULT_STORE}/domain/{DEFAULT_DOMAIN}/credential/test-cred/updateCredentials" in req_url

    @responses.activate
    def test_update_returns_error(self, client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            _update_url(SAMPLE_CRED_ID),
            status=400,
            body="Invalid XML",
        )

        with pytest.raises(JenkinsAPIError, match="400"):
            update_credential(client, SAMPLE_CRED_ID, "<bad-xml>")


# ==================================================================
# delete_credential
# ==================================================================


class TestDeleteCredential:
    @responses.activate
    def test_delete_success(self, client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(responses.POST, _delete_url(SAMPLE_CRED_ID), status=200)

        resp = delete_credential(client, SAMPLE_CRED_ID)
        assert resp.status_code == 200
        # Verify URL
        post_call = responses.calls[1]
        assert f"/credential/{SAMPLE_CRED_ID}/doDelete" in post_call.request.url

    @responses.activate
    def test_delete_custom_store(self, client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            _delete_url("folder-cred", store="folder-store"),
            status=200,
        )
        resp = delete_credential(client, "folder-cred", store="folder-store")
        assert resp.status_code == 200

    @responses.activate
    def test_delete_default_store(self, client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            _delete_url("test-cred", store=DEFAULT_STORE),
            status=200,
        )
        delete_credential(client, "test-cred")
        req_url = responses.calls[1].request.url
        assert f"/store/{DEFAULT_STORE}" in req_url
        assert "/doDelete" in req_url

    @responses.activate
    def test_delete_not_found(self, client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            _delete_url("no-such-cred"),
            status=404,
        )
        with pytest.raises(JenkinsNotFoundError):
            delete_credential(client, "no-such-cred")

    @responses.activate
    def test_delete_sends_form_data(self, client: JenkinsClient) -> None:
        """Delete should POST with form-encoded data."""
        _register_crumb(responses)
        responses.add(responses.POST, _delete_url(SAMPLE_CRED_ID), status=200)

        delete_credential(client, SAMPLE_CRED_ID)
        post_call = responses.calls[1]
        assert (
            "application/x-www-form-urlencoded"
            in post_call.request.headers["Content-Type"]
        )


# ==================================================================
# Edge cases
# ==================================================================


class TestEdgeCases:
    @responses.activate
    def test_special_characters_in_cred_id(self, client: JenkinsClient) -> None:
        """Credential IDs with special characters should work."""
        cred_id = "my/credential@v1.0#test"
        _register_crumb(responses)
        url = _get_url(cred_id)
        responses.add(responses.GET, url, json=SAMPLE_GET_RESPONSE, status=200)

        result = get_credential(client, cred_id)
        assert result == SAMPLE_GET_RESPONSE

    @responses.activate
    def test_unicode_in_description(self, client: JenkinsClient) -> None:
        """Unicode characters in credential description."""
        responses.add(
            responses.GET,
            _get_url("unicode-cred"),
            json={
                "id": "unicode-cred",
                "typeName": "Username with password",
                "description": "中文描述 — テスト",
            },
            status=200,
        )
        result = get_credential(client, "unicode-cred")
        assert result["description"] == "中文描述 — テスト"

    @responses.activate
    def test_create_unicode_xml(self, client: JenkinsClient) -> None:
        """XML with unicode should be encoded and sent correctly."""
        _register_crumb(responses)
        responses.add(responses.POST, _create_url(), status=200)

        xml = SAMPLE_XML.replace("My credential", "中文凭证")
        resp = create_credential(client, xml)
        assert resp.status_code == 200
        body = responses.calls[1].request.body
        assert "中文凭证".encode("utf-8") in body


# ==================================================================
# CLI tests — credential
# ==================================================================


def _mock_cfg():
    return (
        patch("jcli.sdk.config.Config.load", return_value=None),
        patch("jcli.sdk.config.Config.get_active_profile", return_value={
            "url": BASE_URL, "username": "admin", "api_token": "fake-token",
        }),
        patch("jcli.sdk.config.Config.get_profile", return_value={
            "url": BASE_URL, "username": "admin", "api_token": "fake-token",
        }),
    )


class TestCLICredentialList:
    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_list_credentials_table(self, mock_gp, mock_gap, mock_load) -> None:
        mock_gp.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        mock_gap.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        responses.add(
            responses.GET,
            f"{BASE_URL}/credentials/store/{DEFAULT_STORE}/domain/{DEFAULT_DOMAIN}/api/json",
            json={
                "credentials": [
                    {"id": "github-token", "typeName": "Secret text", "description": "GitHub token"},
                    {"id": "deploy-key", "typeName": "SSH key", "description": "Deploy key"},
                ]
            },
            status=200,
        )

        runner = CliRunner()
        from jcli.plugins.credential import credential_group

        result = runner.invoke(credential_group, ["list"], obj={"format": "table"})
        assert result.exit_code == 0
        assert "github-token" in result.output
        assert "deploy-key" in result.output

    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_list_credentials_empty(self, mock_gp, mock_gap, mock_load) -> None:
        mock_gp.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        mock_gap.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        responses.add(
            responses.GET,
            f"{BASE_URL}/credentials/store/{DEFAULT_STORE}/domain/{DEFAULT_DOMAIN}/api/json",
            json={"credentials": []},
            status=200,
        )

        runner = CliRunner()
        from jcli.plugins.credential import credential_group

        result = runner.invoke(credential_group, ["list"], obj={"format": "table"})
        assert result.exit_code == 0
        assert "No credentials found" in result.output


class TestCLICredentialGet:
    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_get_credential_json(self, mock_gp, mock_gap, mock_load) -> None:
        mock_gp.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        mock_gap.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        responses.add(
            responses.GET,
            f"{BASE_URL}/credentials/store/{DEFAULT_STORE}/domain/{DEFAULT_DOMAIN}/credential/github-token/api/json",
            json={"id": "github-token", "typeName": "Secret text", "description": "Token"},
            status=200,
        )

        runner = CliRunner()
        from jcli.plugins.credential import credential_group

        result = runner.invoke(credential_group, ["get", "github-token"], obj={"format": "json"})
        assert result.exit_code == 0
        parsed = __import__("json").loads(result.output)
        assert parsed["id"] == "github-token"

    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_get_credential_not_found(self, mock_gp, mock_gap, mock_load) -> None:
        mock_gp.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        mock_gap.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        responses.add(
            responses.GET,
            f"{BASE_URL}/credentials/store/{DEFAULT_STORE}/domain/{DEFAULT_DOMAIN}/credential/nonexistent/api/json",
            status=404,
        )

        runner = CliRunner()
        from jcli.plugins.credential import credential_group

        result = runner.invoke(credential_group, ["get", "nonexistent"], obj={"format": "table"})
        assert result.exit_code != 0


class TestCLICredentialCreate:
    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_create_credential(self, mock_gp, mock_gap, mock_load) -> None:
        mock_gp.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        mock_gap.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/credentials/store/{DEFAULT_STORE}/domain/{DEFAULT_DOMAIN}/createCredentials",
            status=200,
        )

        xml_content = SAMPLE_XML
        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(xml_content)
            f.flush()
            tmp_path = f.name

        try:
            runner = CliRunner()
            from jcli.plugins.credential import credential_group

            result = runner.invoke(
                credential_group,
                ["create", "my-cred-id", tmp_path],
                obj={"format": "table"},
            )
            assert result.exit_code == 0
            assert "created" in result.output.lower()
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestCLICredentialUpdate:
    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_update_credential(self, mock_gp, mock_gap, mock_load) -> None:
        mock_gp.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        mock_gap.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/credentials/store/{DEFAULT_STORE}/domain/{DEFAULT_DOMAIN}/credential/my-cred-id/updateCredentials",
            status=200,
        )

        xml_content = SAMPLE_XML
        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(xml_content)
            f.flush()
            tmp_path = f.name

        try:
            runner = CliRunner()
            from jcli.plugins.credential import credential_group

            result = runner.invoke(
                credential_group,
                ["update", "my-cred-id", tmp_path],
                obj={"format": "table"},
            )
            assert result.exit_code == 0
            assert "updated" in result.output.lower()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_update_credential_with_store(self, mock_gp, mock_gap, mock_load) -> None:
        mock_gp.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        mock_gap.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/credentials/store/folder-store/domain/{DEFAULT_DOMAIN}/credential/my-cred-id/updateCredentials",
            status=200,
        )

        xml_content = SAMPLE_XML
        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(xml_content)
            f.flush()
            tmp_path = f.name

        try:
            runner = CliRunner()
            from jcli.plugins.credential import credential_group

            result = runner.invoke(
                credential_group,
                ["update", "my-cred-id", tmp_path, "--store", "folder-store"],
                obj={"format": "table"},
            )
            assert result.exit_code == 0
            assert "updated" in result.output.lower()
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestCLICredentialDelete:
    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_delete_with_force(self, mock_gp, mock_gap, mock_load) -> None:
        mock_gp.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        mock_gap.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/credentials/store/{DEFAULT_STORE}/domain/{DEFAULT_DOMAIN}/credential/old-token/doDelete",
            status=200,
        )

        runner = CliRunner()
        from jcli.plugins.credential import credential_group

        result = runner.invoke(
            credential_group,
            ["delete", "old-token", "--force"],
            obj={"format": "table"},
        )
        assert result.exit_code == 0
        assert "deleted" in result.output.lower()

    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_delete_no_confirm_aborts(self, mock_gp, mock_gap, mock_load) -> None:
        mock_gp.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        mock_gap.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        runner = CliRunner()
        from jcli.plugins.credential import credential_group

        result = runner.invoke(
            credential_group,
            ["delete", "old-token"],
            input="n\n",
            obj={"format": "table"},
        )
        assert result.exit_code != 0
