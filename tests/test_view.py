"""Tests for jcli.sdk.view — Jenkins View SDK functions."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch

import pytest
import responses
from click.testing import CliRunner

from jcli.sdk.client import JenkinsClient
from jcli.sdk.exceptions import (
    JenkinsAPIError,
    JenkinsNotFoundError,
)
from jcli.sdk.view import (
    create_view,
    delete_view,
    get_view,
    list_views,
    update_view,
)

BASE_URL = "http://jenkins.example.com"
CRUMB_URL = f"{BASE_URL}/crumbIssuer/api/json"
CRUMB_RESPONSE = {
    "crumb": "abc123",
    "crumbRequestField": "Jenkins-Crumb",
}

SAMPLE_VIEWS = {
    "views": [
        {
            "name": "All",
            "url": f"{BASE_URL}/view/All/",
            "jobs": [
                {"name": "job-1", "url": f"{BASE_URL}/job/job-1/"},
                {"name": "job-2", "url": f"{BASE_URL}/job/job-2/"},
            ],
        },
        {
            "name": "Production",
            "url": f"{BASE_URL}/view/Production/",
            "jobs": [
                {"name": "deploy-app", "url": f"{BASE_URL}/job/deploy-app/"},
            ],
        },
    ]
}

SAMPLE_VIEW_DETAIL = {
    "name": "All",
    "url": f"{BASE_URL}/view/All/",
    "description": "Default view",
    "jobs": [
        {"name": "job-1", "color": "blue"},
        {"name": "job-2", "color": "red"},
    ],
}

EMPTY_VIEWS = {"views": []}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _register_crumb(rsps: responses.RequestsMock) -> None:
    rsps.add(responses.GET, CRUMB_URL, json=CRUMB_RESPONSE, status=200)


def _bypass_crumb(client: JenkinsClient) -> None:
    """Set dummy crumb headers to skip crumb fetch during tests."""
    client._crumb_header = "Jenkins-Crumb"
    client._crumb_value = "dummy"


# ==================================================================
# list_views
# ==================================================================


class TestListViews:
    @responses.activate
    def test_list_views_basic(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json",
            json=SAMPLE_VIEWS,
            status=200,
        )

        result = list_views(jenkins_client)

        assert len(result) == 2
        assert result[0]["name"] == "All"
        assert result[1]["name"] == "Production"
        # Verify tree param
        assert "tree=views" in responses.calls[0].request.url

    @responses.activate
    def test_list_views_empty(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json",
            json=EMPTY_VIEWS,
            status=200,
        )

        result = list_views(jenkins_client)
        assert result == []

    @responses.activate
    def test_list_views_jobs_included(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json",
            json=SAMPLE_VIEWS,
            status=200,
        )

        result = list_views(jenkins_client)
        assert len(result[0]["jobs"]) == 2
        assert result[0]["jobs"][0]["name"] == "job-1"

    @responses.activate
    def test_list_views_api_error(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json",
            status=500,
        )

        with pytest.raises(JenkinsAPIError):
            list_views(jenkins_client)


# ==================================================================
# get_view
# ==================================================================


class TestGetView:
    @responses.activate
    def test_get_view_basic(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/view/All/api/json",
            json=SAMPLE_VIEW_DETAIL,
            status=200,
        )

        result = get_view(jenkins_client, "All")

        assert result["name"] == "All"
        assert result["description"] == "Default view"
        assert len(result["jobs"]) == 2

    @responses.activate
    def test_get_view_with_special_chars(self, jenkins_client: JenkinsClient) -> None:
        view_name = "My Production View"
        responses.add(
            responses.GET,
            f"{BASE_URL}/view/My%20Production%20View/api/json",
            json={"name": view_name, "url": f"{BASE_URL}/view/My%20Production%20View/"},
            status=200,
        )

        result = get_view(jenkins_client, view_name)
        assert result["name"] == view_name

    @responses.activate
    def test_get_view_not_found(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/view/Nonexistent/api/json",
            status=404,
        )

        with pytest.raises(JenkinsNotFoundError):
            get_view(jenkins_client, "Nonexistent")

    @responses.activate
    def test_get_view_empty_jobs(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/view/Empty/api/json",
            json={"name": "Empty", "url": f"{BASE_URL}/view/Empty/", "jobs": []},
            status=200,
        )

        result = get_view(jenkins_client, "Empty")
        assert result["name"] == "Empty"
        assert result["jobs"] == []


# ==================================================================
# create_view
# ==================================================================


class TestCreateView:
    @responses.activate
    def test_create_view_basic(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/createView?name=MyView",
            status=200,
        )

        config_xml = '<hudson.model.ListView><name>MyView</name></hudson.model.ListView>'
        create_view(jenkins_client, "MyView", config_xml)

        post_call = responses.calls[1]
        assert post_call.request.url.endswith("createView?name=MyView")
        assert post_call.request.headers["Content-Type"] == "application/xml"
        assert b"MyView" in (post_call.request.body or b"")

    @responses.activate
    def test_create_view_already_exists(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/createView?name=DuplicateView",
            status=400,
        )

        with pytest.raises(JenkinsAPIError) as exc_info:
            create_view(jenkins_client, "DuplicateView", "<view/>")
        assert exc_info.value.status_code == 400

    @responses.activate
    def test_create_view_unauthorized(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/createView?name=Unauthorized",
            status=401,
        )

        from jcli.sdk.exceptions import JenkinsAuthError

        with pytest.raises(JenkinsAuthError):
            create_view(jenkins_client, "Unauthorized", "<view/>")

    @responses.activate
    def test_create_view_unicode_name(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/createView?name=%E6%B5%8B%E8%AF%95",
            status=200,
        )

        create_view(jenkins_client, "测试", "<view/>")
        post_call = responses.calls[1]
        assert "%E6%B5%8B%E8%AF%95" in post_call.request.url


# ==================================================================
# delete_view
# ==================================================================


class TestDeleteView:
    @responses.activate
    def test_delete_view_basic(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/view/OldView/doDelete",
            status=302,
        )

        delete_view(jenkins_client, "OldView")

        post_call = responses.calls[1]
        assert "OldView/doDelete" in post_call.request.url

    @responses.activate
    def test_delete_view_not_found(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/view/Nonexistent/doDelete",
            status=404,
        )

        with pytest.raises(JenkinsNotFoundError):
            delete_view(jenkins_client, "Nonexistent")

    @responses.activate
    def test_delete_view_forbidden(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/view/Protected/doDelete",
            status=403,
        )

        with pytest.raises(JenkinsAPIError) as exc_info:
            delete_view(jenkins_client, "Protected")
        assert exc_info.value.status_code == 403


# ==================================================================
# update_view
# ==================================================================


class TestUpdateView:
    @responses.activate
    def test_update_view_basic(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/view/MyView/config.xml",
            status=200,
        )

        config_xml = '<hudson.model.ListView><name>MyView</name></hudson.model.ListView>'
        update_view(jenkins_client, "MyView", config_xml)

        post_call = responses.calls[1]
        assert post_call.request.url.endswith("MyView/config.xml")
        assert post_call.request.headers["Content-Type"] == "application/xml"
        assert b"MyView" in (post_call.request.body or b"")

    @responses.activate
    def test_update_view_bytes(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/view/MyView/config.xml",
            status=200,
        )

        config_xml = b'<hudson.model.ListView><name>MyView</name></hudson.model.ListView>'
        update_view(jenkins_client, "MyView", config_xml)

        post_call = responses.calls[1]
        assert b"MyView" in (post_call.request.body or b"")

    @responses.activate
    def test_update_view_not_found(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/view/Nonexistent/config.xml",
            status=404,
        )

        with pytest.raises(JenkinsNotFoundError):
            update_view(jenkins_client, "Nonexistent", "<view/>")

    @responses.activate
    def test_update_view_api_error(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/view/Failing/config.xml",
            status=500,
        )

        with pytest.raises(JenkinsAPIError) as exc_info:
            update_view(jenkins_client, "Failing", "<view/>")
        assert exc_info.value.status_code == 500


# ==================================================================
# CLI commands
# ==================================================================


class TestViewCliCommands:
    """Test the Click CLI view commands via CliRunner."""

    @staticmethod
    def _mock_config_for_cli(profile_name: str = "default") -> dict:
        """Return a mock profile dict for Config.get_profile()."""
        return {
            "url": "http://jenkins.example.com",
            "username": "admin",
            "api_token": "fake-token",
        }

    # --- list ---

    @responses.activate
    def test_cli_list_table(self) -> None:
        """Test 'jcli view list' with table output."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json",
            json=SAMPLE_VIEWS,
            status=200,
        )

        with patch("jcli.sdk.config.Config.load", return_value=None), \
             patch("jcli.sdk.config.Config.get_active_profile_name", return_value="default"), \
             patch("jcli.sdk.config.Config.get_profile", return_value=self._mock_config_for_cli()):
            runner = CliRunner()
            from jcli.plugins.view import view_group

            result = runner.invoke(view_group, ["list"])
            assert result.exit_code == 0
            assert "All (2 jobs)" in result.output
            assert "Production (1 jobs)" in result.output

    @responses.activate
    def test_cli_list_json(self) -> None:
        """Test 'jcli view list' with JSON output."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json",
            json=SAMPLE_VIEWS,
            status=200,
        )

        with patch("jcli.sdk.config.Config.load", return_value=None), \
             patch("jcli.sdk.config.Config.get_active_profile_name", return_value="default"), \
             patch("jcli.sdk.config.Config.get_profile", return_value=self._mock_config_for_cli()):
            runner = CliRunner()
            from jcli.plugins.view import view_group

            result = runner.invoke(
                view_group,
                ["list"],
                obj={"format": "json"},
            )
            assert result.exit_code == 0
            parsed = __import__("json").loads(result.output)
            assert len(parsed) == 2
            assert parsed[0]["name"] == "All"

    @responses.activate
    def test_cli_list_empty(self) -> None:
        """Test 'jcli view list' with no views."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json",
            json=EMPTY_VIEWS,
            status=200,
        )

        with patch("jcli.sdk.config.Config.load", return_value=None), \
             patch("jcli.sdk.config.Config.get_active_profile_name", return_value="default"), \
             patch("jcli.sdk.config.Config.get_profile", return_value=self._mock_config_for_cli()):
            runner = CliRunner()
            from jcli.plugins.view import view_group

            result = runner.invoke(view_group, ["list"])
            assert result.exit_code == 0
            assert "No views found" in result.output

    # --- get ---

    @responses.activate
    def test_cli_get_table(self) -> None:
        """Test 'jcli view get <name>' with table output."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/view/All/api/json",
            json=SAMPLE_VIEW_DETAIL,
            status=200,
        )

        with patch("jcli.sdk.config.Config.load", return_value=None), \
             patch("jcli.sdk.config.Config.get_active_profile_name", return_value="default"), \
             patch("jcli.sdk.config.Config.get_profile", return_value=self._mock_config_for_cli()):
            runner = CliRunner()
            from jcli.plugins.view import view_group

            result = runner.invoke(view_group, ["get", "All"])
            assert result.exit_code == 0
            assert "Name:" in result.output
            assert "Default view" in result.output
            assert "job-1" in result.output

    @responses.activate
    def test_cli_get_json(self) -> None:
        """Test 'jcli view get <name>' with JSON output."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/view/All/api/json",
            json=SAMPLE_VIEW_DETAIL,
            status=200,
        )

        with patch("jcli.sdk.config.Config.load", return_value=None), \
             patch("jcli.sdk.config.Config.get_active_profile_name", return_value="default"), \
             patch("jcli.sdk.config.Config.get_profile", return_value=self._mock_config_for_cli()):
            runner = CliRunner()
            from jcli.plugins.view import view_group

            result = runner.invoke(
                view_group,
                ["get", "All"],
                obj={"format": "json"},
            )
            assert result.exit_code == 0
            parsed = __import__("json").loads(result.output)
            assert parsed["name"] == "All"

    # --- create ---

    @responses.activate
    def test_cli_create(self) -> None:
        """Test 'jcli view create <name> <file>'."""
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/createView?name=NewView",
            status=200,
        )

        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write('<hudson.model.ListView><name>NewView</name></hudson.model.ListView>')
            f.flush()
            tmp_path = f.name

        try:
            with patch("jcli.sdk.config.Config.load", return_value=None), \
                 patch("jcli.sdk.config.Config.get_active_profile_name", return_value="default"), \
                 patch("jcli.sdk.config.Config.get_profile", return_value=self._mock_config_for_cli()):
                runner = CliRunner()
                from jcli.plugins.view import view_group

                result = runner.invoke(view_group, ["create", "NewView", tmp_path])
                assert result.exit_code == 0
                assert "created successfully" in result.output
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @responses.activate
    def test_cli_create_file_not_found(self) -> None:
        """Test 'jcli view create' with missing config file."""
        with patch("jcli.sdk.config.Config.load", return_value=None), \
             patch("jcli.sdk.config.Config.get_active_profile_name", return_value="default"), \
             patch("jcli.sdk.config.Config.get_profile", return_value=self._mock_config_for_cli()):
            runner = CliRunner()
            from jcli.plugins.view import view_group

            result = runner.invoke(view_group, ["create", "Test", "/nonexistent/file.xml"])
            assert result.exit_code != 0

    # --- delete ---

    @responses.activate
    def test_cli_delete_yes_flag(self) -> None:
        """Test 'jcli view delete --yes <name>'."""
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/view/OldView/doDelete",
            status=302,
        )

        with patch("jcli.sdk.config.Config.load", return_value=None), \
             patch("jcli.sdk.config.Config.get_active_profile_name", return_value="default"), \
             patch("jcli.sdk.config.Config.get_profile", return_value=self._mock_config_for_cli()):
            runner = CliRunner()
            from jcli.plugins.view import view_group

            result = runner.invoke(view_group, ["delete", "--yes", "OldView"])
            assert result.exit_code == 0
            assert "deleted successfully" in result.output

    @responses.activate
    def test_cli_delete_no_confirm(self) -> None:
        """Test 'jcli view delete' with confirmation abort."""
        with patch("jcli.sdk.config.Config.load", return_value=None), \
             patch("jcli.sdk.config.Config.get_active_profile_name", return_value="default"), \
             patch("jcli.sdk.config.Config.get_profile", return_value=self._mock_config_for_cli()):
            runner = CliRunner()
            from jcli.plugins.view import view_group

            result = runner.invoke(view_group, ["delete", "OldView"], input="n\n")
            assert result.exit_code != 0

    # --- update ---

    @responses.activate
    def test_cli_update(self) -> None:
        """Test 'jcli view update <name> <file>'."""
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/view/MyView/config.xml",
            status=200,
        )

        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write('<hudson.model.ListView><name>MyView</name></hudson.model.ListView>')
            f.flush()
            tmp_path = f.name

        try:
            with patch("jcli.sdk.config.Config.load", return_value=None), \
                 patch("jcli.sdk.config.Config.get_active_profile_name", return_value="default"), \
                 patch("jcli.sdk.config.Config.get_profile", return_value=self._mock_config_for_cli()):
                runner = CliRunner()
                from jcli.plugins.view import view_group

                result = runner.invoke(view_group, ["update", "MyView", tmp_path])
                assert result.exit_code == 0
                assert "updated" in result.output
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @responses.activate
    def test_cli_update_not_found(self) -> None:
        """Test 'jcli view update' with nonexistent view."""
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/view/Nonexistent/config.xml",
            status=404,
        )

        with NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write('<hudson.model.ListView/>')
            f.flush()
            tmp_path = f.name

        try:
            with patch("jcli.sdk.config.Config.load", return_value=None), \
                 patch("jcli.sdk.config.Config.get_active_profile_name", return_value="default"), \
                 patch("jcli.sdk.config.Config.get_profile", return_value=self._mock_config_for_cli()):
                runner = CliRunner()
                from jcli.plugins.view import view_group

                result = runner.invoke(view_group, ["update", "Nonexistent", tmp_path])
                assert result.exit_code == 0
                assert "Error" in result.output
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @responses.activate
    def test_cli_update_file_not_found(self) -> None:
        """Test 'jcli view update' with missing config file."""
        with patch("jcli.sdk.config.Config.load", return_value=None), \
             patch("jcli.sdk.config.Config.get_active_profile_name", return_value="default"), \
             patch("jcli.sdk.config.Config.get_profile", return_value=self._mock_config_for_cli()):
            runner = CliRunner()
            from jcli.plugins.view import view_group

            result = runner.invoke(view_group, ["update", "Test", "/nonexistent/file.xml"])
            assert result.exit_code != 0

    # --- yaml format ---

    @responses.activate
    def test_cli_list_yaml(self) -> None:
        """Test 'jcli view list' with YAML output."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json",
            json=SAMPLE_VIEWS,
            status=200,
        )

        with patch("jcli.sdk.config.Config.load", return_value=None), \
             patch("jcli.sdk.config.Config.get_active_profile_name", return_value="default"), \
             patch("jcli.sdk.config.Config.get_profile", return_value=self._mock_config_for_cli()):
            runner = CliRunner()
            from jcli.plugins.view import view_group

            result = runner.invoke(
                view_group,
                ["list"],
                obj={"format": "yaml"},
            )
            assert result.exit_code == 0
            assert "name: All" in result.output
