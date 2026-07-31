"""Tests for jcli.sdk.plugin — Plugin management SDK functions."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import patch

import pytest
import responses
from click.testing import CliRunner

from jcli.sdk.client import JenkinsClient
from jcli.sdk.exceptions import (
    JenkinsAPIError,
    JenkinsNotFoundError,
)
from jcli.sdk.plugin import (
    _build_install_xml,
    check_plugin_updates,
    get_plugin,
    install_plugins,
    list_plugins,
    uninstall_plugin,
)

BASE_URL = "http://jenkins.example.com"
PLUGIN_API_URL = f"{BASE_URL}/pluginManager/api/json"
INSTALL_URL = f"{BASE_URL}/pluginManager/installNecessaryPlugins"

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def make_client(**kwargs) -> JenkinsClient:
    """Create a JenkinsClient with default test credentials."""
    defaults = {"base_url": BASE_URL, "username": "admin", "token": "fake-token"}
    defaults.update(kwargs)
    return JenkinsClient(**defaults)


SAMPLE_PLUGINS_RESPONSE = {
    "plugins": [
        {"shortName": "git", "version": "5.0.0", "active": True, "hasUpdate": False},
        {"shortName": "workflow-aggregator", "version": "2.7", "active": True, "hasUpdate": True},
        {"shortName": "blueocean", "version": "1.27.0", "active": False, "hasUpdate": False},
    ]
}

SAMPLE_DETAIL_RESPONSE = {
    "plugins": [
        {
            "shortName": "git",
            "version": "5.0.0",
            "active": True,
            "hasUpdate": False,
            "longName": "Git plugin",
            "url": "https://plugins.jenkins.io/git",
            "requiredCoreVersion": "2.346",
            "hasRequireRestart": False,
        },
        {
            "shortName": "workflow-aggregator",
            "version": "2.7",
            "active": True,
            "hasUpdate": True,
            "longName": "Pipeline Aggregator",
            "url": "https://plugins.jenkins.io/workflow-aggregator",
            "requiredCoreVersion": "2.319",
            "hasRequireRestart": False,
        },
    ]
}


# ==================================================================
# _build_install_xml helper
# ==================================================================


class TestBuildInstallXml:
    def test_single_plugin_no_version(self) -> None:
        xml = _build_install_xml({"git": None})
        assert "<install plugin=\"git\" />" in xml
        assert xml.startswith("<jenkins>")
        assert xml.endswith("</jenkins>")

    def test_single_plugin_with_version(self) -> None:
        xml = _build_install_xml({"git": "5.0.0"})
        assert '<install plugin="git@5.0.0" />' in xml

    def test_multiple_plugins(self) -> None:
        xml = _build_install_xml({"git": "5.0.0", "workflow-aggregator": None})
        assert '<install plugin="git@5.0.0" />' in xml
        assert '<install plugin="workflow-aggregator" />' in xml

    def test_empty_dict(self) -> None:
        xml = _build_install_xml({})
        assert xml == "<jenkins>\n</jenkins>"


# ==================================================================
# list_plugins
# ==================================================================


class TestListPlugins:
    @responses.activate
    def test_list_plugins_success(self) -> None:
        responses.add(
            responses.GET,
            PLUGIN_API_URL,
            json=SAMPLE_PLUGINS_RESPONSE,
            status=200,
        )
        client = make_client()
        result = list_plugins(client)

        assert len(result) == 3
        assert result[0]["shortName"] == "git"
        assert result[0]["version"] == "5.0.0"
        assert result[0]["active"] is True
        assert result[0]["hasUpdate"] is False

    @responses.activate
    def test_list_plugins_empty(self) -> None:
        responses.add(
            responses.GET,
            PLUGIN_API_URL,
            json={"plugins": []},
            status=200,
        )
        client = make_client()
        result = list_plugins(client)

        assert result == []

    @responses.activate
    def test_list_plugins_no_plugins_key(self) -> None:
        """Graceful handling of response missing 'plugins' key."""
        responses.add(
            responses.GET,
            PLUGIN_API_URL,
            json={},
            status=200,
        )
        client = make_client()
        result = list_plugins(client)

        assert result == []

    @responses.activate
    def test_list_plugins_includes_tree_param(self) -> None:
        responses.add(
            responses.GET,
            PLUGIN_API_URL,
            json=SAMPLE_PLUGINS_RESPONSE,
            status=200,
        )
        client = make_client()
        list_plugins(client)

        url = responses.calls[0].request.url
        assert "tree=" in url
        assert "shortName" in url
        assert "version" in url


# ==================================================================
# get_plugin
# ==================================================================


class TestGetPlugin:
    @responses.activate
    def test_get_plugin_found(self) -> None:
        responses.add(
            responses.GET,
            PLUGIN_API_URL,
            json=SAMPLE_DETAIL_RESPONSE,
            status=200,
        )
        client = make_client()
        result = get_plugin(client, "git")

        assert result is not None
        assert result["shortName"] == "git"
        assert result["longName"] == "Git plugin"
        assert result["requiredCoreVersion"] == "2.346"

    @responses.activate
    def test_get_plugin_not_found(self) -> None:
        responses.add(
            responses.GET,
            PLUGIN_API_URL,
            json=SAMPLE_DETAIL_RESPONSE,
            status=200,
        )
        client = make_client()

        with pytest.raises(JenkinsNotFoundError, match="nonexistent"):
            get_plugin(client, "nonexistent")

    @responses.activate
    def test_get_plugin_empty_plugins(self) -> None:
        responses.add(
            responses.GET,
            PLUGIN_API_URL,
            json={"plugins": []},
            status=200,
        )
        client = make_client()

        with pytest.raises(JenkinsNotFoundError):
            get_plugin(client, "git")


# ==================================================================
# install_plugins
# ==================================================================


class TestInstallPlugins:
    @responses.activate
    def test_install_single_plugin(self) -> None:
        # Need crumb for POST
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        responses.add(responses.POST, INSTALL_URL, status=200)

        client = make_client()
        install_plugins(client, {"git": None})

        body = responses.calls[1].request.body
        assert b'<install plugin="git" />' in body

    @responses.activate
    def test_install_plugin_with_version(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        responses.add(responses.POST, INSTALL_URL, status=200)

        client = make_client()
        install_plugins(client, {"git": "5.0.0"})

        body = responses.calls[1].request.body
        assert b'<install plugin="git@5.0.0" />' in body

    @responses.activate
    def test_install_multiple_plugins(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        responses.add(responses.POST, INSTALL_URL, status=200)

        client = make_client()
        install_plugins(client, {"git": "5.0.0", "workflow-aggregator": None})

        body = responses.calls[1].request.body.decode()
        assert 'plugin="git@5.0.0"' in body
        assert 'plugin="workflow-aggregator"' in body

    @responses.activate
    def test_install_empty_dict_does_nothing(self) -> None:
        """Empty dict should not make any HTTP request."""
        client = make_client()
        install_plugins(client, {})

        # No HTTP calls should be made
        assert len(responses.calls) == 0

    @responses.activate
    def test_install_uses_xml_content_type(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        responses.add(responses.POST, INSTALL_URL, status=200)

        client = make_client()
        install_plugins(client, {"git": None})

        ct = responses.calls[1].request.headers["Content-Type"]
        assert "application/xml" in ct

    @responses.activate
    def test_install_api_error_propagates(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        responses.add(responses.POST, INSTALL_URL, status=400)

        client = make_client()
        with pytest.raises(JenkinsAPIError, match="400"):
            install_plugins(client, {"bad-plugin": None})


# ==================================================================
# uninstall_plugin
# ==================================================================


class TestUninstallPlugin:
    @responses.activate
    def test_uninstall_success(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        uninstall_url = f"{BASE_URL}/pluginManager/plugin/git/doUninstall"
        responses.add(responses.POST, uninstall_url, status=200)

        client = make_client()
        uninstall_plugin(client, "git")

        assert len(responses.calls) == 2  # crumb + uninstall

    @responses.activate
    def test_uninstall_url_correct(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        uninstall_url = f"{BASE_URL}/pluginManager/plugin/workflow-aggregator/doUninstall"
        responses.add(responses.POST, uninstall_url, status=200)

        client = make_client()
        uninstall_plugin(client, "workflow-aggregator")

        assert responses.calls[1].request.url == uninstall_url

    @responses.activate
    def test_uninstall_api_error_propagates(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        uninstall_url = f"{BASE_URL}/pluginManager/plugin/nonexistent/doUninstall"
        responses.add(responses.POST, uninstall_url, status=404)

        client = make_client()
        with pytest.raises(JenkinsNotFoundError, match="404"):
            uninstall_plugin(client, "nonexistent")


# ==================================================================
# CLI commands
# ==================================================================


class TestPluginCLI:
    """Test CLI commands via Click's CliRunner."""

    @pytest.fixture
    def runner(self):
        from click.testing import CliRunner
        return CliRunner()

    @pytest.fixture
    def cli(self):
        from jcli.cli import cli
        return cli

    # ----- list -----

    def test_list_command_help(self, runner, cli):
        result = runner.invoke(cli, ["plugin", "list", "--help"])
        assert result.exit_code == 0
        assert "List installed" in result.output

    def test_list_command_no_config(self, runner, cli, monkeypatch):
        """Without a config file, should show error."""
        monkeypatch.setattr("jcli.sdk.config.DEFAULT_CONFIG_FILE", "/tmp/nonexistent_jcli_config.yaml")
        result = runner.invoke(cli, ["plugin", "list"])
        # Should fail because config doesn't exist in test environment
        assert result.exit_code != 0

    # ----- get -----

    def test_get_command_help(self, runner, cli):
        result = runner.invoke(cli, ["plugin", "get", "--help"])
        assert result.exit_code == 0
        assert "details" in result.output.lower() or "NAME" in result.output

    # ----- install -----

    def test_install_command_help(self, runner, cli):
        result = runner.invoke(cli, ["plugin", "install", "--help"])
        assert result.exit_code == 0
        # cliyard 以参数名生成 metavar（PLUGINS），语义同 v1 的 PLUGIN_SPEC：
        # install 接受一个或多个插件名参数
        assert "PLUGINS" in result.output

    # ----- uninstall -----

    def test_uninstall_command_help(self, runner, cli):
        result = runner.invoke(cli, ["plugin", "uninstall", "--help"])
        assert result.exit_code == 0
        assert "NAME" in result.output


# ==================================================================
# _parse_plugin_spec (tested indirectly via install_cmd, but also direct)
# ==================================================================

class TestParsePluginSpec:
    def test_name_only(self) -> None:
        from jcli.plugins.plugin import _parse_plugin_spec
        name, version = _parse_plugin_spec("git")
        assert name == "git"
        assert version is None

    def test_name_with_version(self) -> None:
        from jcli.plugins.plugin import _parse_plugin_spec
        name, version = _parse_plugin_spec("git@5.0.0")
        assert name == "git"
        assert version == "5.0.0"

    def test_name_with_at_in_version(self) -> None:
        """Only first @ splits name from version."""
        from jcli.plugins.plugin import _parse_plugin_spec
        name, version = _parse_plugin_spec("my-plugin@1.0@extra")
        assert name == "my-plugin"
        assert version == "1.0@extra"

    def test_empty_string(self) -> None:
        from jcli.plugins.plugin import _parse_plugin_spec
        name, version = _parse_plugin_spec("")
        assert name == ""
        assert version is None


# ==================================================================
# Full CLI tests with mocked responses
# ==================================================================


def _mock_config():
    return (
        patch("jcli.sdk.config.Config.load", return_value=None),
        patch("jcli.sdk.config.Config.get_active_profile", return_value={
            "url": BASE_URL, "username": "admin", "api_token": "fake-token",
        }),
        patch("jcli.sdk.config.Config.get_profile", return_value={
            "url": BASE_URL, "username": "admin", "api_token": "fake-token",
        }),
    )


class TestPluginCLIListMocked:
    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_list_plugins_table(self, mock_gp, mock_gap, mock_load) -> None:
        mock_gp.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        mock_gap.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        responses.add(
            responses.GET,
            PLUGIN_API_URL,
            json={
                "plugins": [
                    {"shortName": "git", "version": "5.0.0", "active": True, "hasUpdate": False},
                    {"shortName": "docker", "version": "1.5", "active": True, "hasUpdate": True},
                ]
            },
            status=200,
        )

        runner = CliRunner()
        from jcli.plugins.plugin import plugin_group

        result = runner.invoke(plugin_group, ["list"], obj={"format": "table"})
        assert result.exit_code == 0
        assert "git" in result.output
        assert "docker" in result.output

    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_list_plugins_empty(self, mock_gp, mock_gap, mock_load) -> None:
        mock_gp.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        mock_gap.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        responses.add(
            responses.GET,
            PLUGIN_API_URL,
            json={"plugins": []},
            status=200,
        )

        runner = CliRunner()
        from jcli.plugins.plugin import plugin_group

        result = runner.invoke(plugin_group, ["list"], obj={"format": "table"})
        assert result.exit_code == 0
        assert "No plugins found" in result.output

    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_list_plugins_json(self, mock_gp, mock_gap, mock_load) -> None:
        mock_gp.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        mock_gap.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        responses.add(
            responses.GET,
            PLUGIN_API_URL,
            json={
                "plugins": [
                    {"shortName": "git", "version": "5.0.0", "active": True, "hasUpdate": False},
                ]
            },
            status=200,
        )

        runner = CliRunner()
        from jcli.plugins.plugin import plugin_group

        result = runner.invoke(plugin_group, ["list"], obj={"format": "json"})
        assert result.exit_code == 0
        assert "git" in result.output
        assert "5.0.0" in result.output


class TestPluginCLIGetMocked:
    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_get_plugin_table(self, mock_gp, mock_gap, mock_load) -> None:
        mock_gp.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        mock_gap.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        responses.add(
            responses.GET,
            PLUGIN_API_URL,
            json={
                "plugins": [
                    {
                        "shortName": "git",
                        "version": "5.0.0",
                        "active": True,
                        "hasUpdate": False,
                        "longName": "Git plugin",
                        "requiredCoreVersion": "2.346",
                    },
                ]
            },
            status=200,
        )

        runner = CliRunner()
        from jcli.plugins.plugin import plugin_group

        result = runner.invoke(plugin_group, ["get", "git"], obj={"format": "table"})
        assert result.exit_code == 0
        assert "git" in result.output
        assert "5.0.0" in result.output

    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_get_plugin_not_found(self, mock_gp, mock_gap, mock_load) -> None:
        mock_gp.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        mock_gap.return_value = {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}
        responses.add(
            responses.GET,
            PLUGIN_API_URL,
            json={"plugins": []},
            status=200,
        )

        runner = CliRunner()
        from jcli.plugins.plugin import plugin_group

        result = runner.invoke(plugin_group, ["get", "nonexistent"], obj={"format": "table"})
        assert result.exit_code != 0


class TestPluginCLIInstallMocked:
    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_install_plugin(self, mock_gp, mock_gap, mock_load) -> None:
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
            INSTALL_URL,
            status=200,
        )

        runner = CliRunner()
        from jcli.plugins.plugin import plugin_group

        result = runner.invoke(plugin_group, ["install", "git"], obj={"format": "table"})
        assert result.exit_code == 0
        assert "installed" in result.output.lower()

    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_install_plugin_with_version(self, mock_gp, mock_gap, mock_load) -> None:
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
            INSTALL_URL,
            status=200,
        )

        runner = CliRunner()
        from jcli.plugins.plugin import plugin_group

        result = runner.invoke(plugin_group, ["install", "git@5.0.0"], obj={"format": "table"})
        assert result.exit_code == 0
        assert "5.0.0" in result.output


class TestPluginCLIUninstallMocked:
    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_uninstall_plugin(self, mock_gp, mock_gap, mock_load) -> None:
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
            f"{BASE_URL}/pluginManager/plugin/git/doUninstall",
            status=200,
        )

        runner = CliRunner()
        from jcli.plugins.plugin import plugin_group

        result = runner.invoke(plugin_group, ["uninstall", "git"], obj={"format": "table"})
        assert result.exit_code == 0
        assert "uninstall" in result.output.lower()


# ==================================================================
# check_plugin_updates SDK
# ==================================================================


class TestCheckPluginUpdates:
    @responses.activate
    def test_check_updates_success(self) -> None:
        """POST /pluginManager/checkUpdates returns JSON with update info."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/pluginManager/checkUpdates",
            json={"status": "ok", "data": {"jobs": []}},
            status=200,
        )
        client = make_client()
        result = check_plugin_updates(client)

        assert result["status"] == "ok"
        assert "data" in result

    @responses.activate
    def test_check_updates_error(self) -> None:
        """Server error propagates as JenkinsAPIError."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/pluginManager/checkUpdates",
            status=500,
        )
        client = make_client()

        with pytest.raises(JenkinsAPIError, match="500"):
            check_plugin_updates(client)


# ==================================================================
# CLI: check-updates
# ==================================================================


class TestPluginCLICheckUpdatesMocked:
    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_check_updates_success(self, mock_gp, mock_gap, mock_load) -> None:
        """check-updates triggers the server and prints info."""
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
            f"{BASE_URL}/pluginManager/checkUpdates",
            json={"status": "ok"},
            status=200,
        )

        runner = CliRunner()
        from jcli.plugins.plugin import plugin_group

        result = runner.invoke(plugin_group, ["check-updates"], obj={"format": "table"})
        assert result.exit_code == 0
        assert "Plugin update check triggered" in result.output

    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_check_updates_error(self, mock_gp, mock_gap, mock_load) -> None:
        """check-updates prints error on API failure."""
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
            f"{BASE_URL}/pluginManager/checkUpdates",
            status=500,
        )

        runner = CliRunner()
        from jcli.plugins.plugin import plugin_group

        result = runner.invoke(plugin_group, ["check-updates"], obj={"format": "table"})
        assert "Error" in result.output


# ==================================================================
# CLI: restart
# ==================================================================


class TestPluginCLIRestartMocked:
    @responses.activate
    @patch("jcli.sdk.config.Config.load", return_value=None)
    @patch("jcli.sdk.config.Config.get_active_profile")
    @patch("jcli.sdk.config.Config.get_profile")
    def test_restart_with_yes_flag(self, mock_gp, mock_gap, mock_load) -> None:
        """restart --yes sends safeRestart without confirmation prompt."""
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
            f"{BASE_URL}/safeRestart",
            status=200,
        )

        runner = CliRunner()
        from jcli.plugins.plugin import plugin_group

        result = runner.invoke(plugin_group, ["restart", "--yes"], obj={"format": "table"})
        assert result.exit_code == 0
        assert "restart initiated" in result.output.lower()
