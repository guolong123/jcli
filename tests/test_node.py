"""Tests for jcli.sdk.node — Node SDK functions and CLI commands."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
import responses
from click.testing import CliRunner

from jcli.sdk.client import JenkinsClient
from jcli.sdk.node import create_node, delete_node, get_node, list_nodes, toggle_offline

# ------------------------------------------------------------------
# Sample data
# ------------------------------------------------------------------

SAMPLE_NODE_LIST = [
    {
        "displayName": "master",
        "offline": False,
        "temporarilyOffline": False,
        "numExecutors": 2,
        "monitorData": {
            "hudson.node_monitors.ArchitectureMonitor": "Linux (amd64)",
        },
    },
    {
        "displayName": "agent-1",
        "offline": True,
        "temporarilyOffline": True,
        "numExecutors": 4,
        "monitorData": {
            "hudson.node_monitors.ArchitectureMonitor": "Linux (amd64)",
        },
    },
]

SAMPLE_NODE_DETAIL = {
    "displayName": "agent-1",
    "description": "Build agent 1",
    "offline": False,
    "temporarilyOffline": False,
    "numExecutors": 4,
    "idle": True,
    "jnlpAgent": True,
    "monitorData": {
        "hudson.node_monitors.ArchitectureMonitor": "Linux (amd64)",
        "hudson.node_monitors.SwapSpaceMonitor": "OK",
    },
}


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def mock_client():
    """Create a MagicMock JenkinsClient with no preset return values."""
    return MagicMock()


# ==================================================================
# list_nodes tests
# ==================================================================


class TestListNodes:
    def test_returns_computer_list(self, mock_client):
        mock_client.get_json.return_value = {"computer": SAMPLE_NODE_LIST}

        result = list_nodes(mock_client)

        assert len(result) == 2
        assert result[0]["displayName"] == "master"
        assert result[1]["displayName"] == "agent-1"
        mock_client.get_json.assert_called_once_with("/computer/api/json")

    def test_empty_list_when_no_nodes(self, mock_client):
        mock_client.get_json.return_value = {"computer": []}

        result = list_nodes(mock_client)

        assert result == []

    def test_missing_computer_key_returns_empty(self, mock_client):
        mock_client.get_json.return_value = {}

        result = list_nodes(mock_client)

        assert result == []


# ==================================================================
# get_node tests
# ==================================================================


class TestGetNode:
    def test_returns_node_details(self, mock_client):
        mock_client.get_json.return_value = SAMPLE_NODE_DETAIL

        result = get_node(mock_client, "agent-1")

        assert result["displayName"] == "agent-1"
        assert result["numExecutors"] == 4
        mock_client.get_json.assert_called_once_with(
            "/computer/agent-1/api/json"
        )

    def test_node_with_special_chars_in_name(self, mock_client):
        mock_client.get_json.return_value = {
            "displayName": "agent (us-east)",
            "offline": False,
        }

        result = get_node(mock_client, "agent (us-east)")

        assert result["displayName"] == "agent (us-east)"
        mock_client.get_json.assert_called_once_with(
            "/computer/agent%20%28us-east%29/api/json"
        )

    def test_builtin_node(self, mock_client):
        mock_client.get_json.return_value = {
            "displayName": "built-in",
            "offline": False,
        }

        result = get_node(mock_client, "built-in")

        assert result["displayName"] == "built-in"


# ==================================================================
# delete_node tests
# ==================================================================


class TestDeleteNode:
    def test_delete_success(self, mock_client):
        resp = MagicMock()
        resp.ok = True
        mock_client.request.return_value = resp

        result = delete_node(mock_client, "agent-1")

        assert result is True
        mock_client.request.assert_called_once_with(
            "POST", "/computer/agent-1/doDelete"
        )

    def test_delete_returns_false_on_error(self, mock_client):
        resp = MagicMock()
        resp.ok = False
        mock_client.request.return_value = resp

        result = delete_node(mock_client, "agent-1")

        assert result is False


# ==================================================================
# toggle_offline tests
# ==================================================================


class TestToggleOffline:
    def test_toggle_without_message(self, mock_client):
        resp = MagicMock()
        resp.ok = True
        mock_client.post_data.return_value = resp

        result = toggle_offline(mock_client, "agent-1")

        assert result is True
        mock_client.post_data.assert_called_once_with(
            "/computer/agent-1/toggleOffline", data={}
        )

    def test_toggle_with_message(self, mock_client):
        resp = MagicMock()
        resp.ok = True
        mock_client.post_data.return_value = resp

        result = toggle_offline(mock_client, "agent-1", msg="Maintenance window")

        assert result is True
        mock_client.post_data.assert_called_once_with(
            "/computer/agent-1/toggleOffline",
            data={"offlineMessage": "Maintenance window"},
        )

    def test_toggle_returns_false_on_error(self, mock_client):
        resp = MagicMock()
        resp.ok = False
        mock_client.post_data.return_value = resp

        result = toggle_offline(mock_client, "agent-1")

        assert result is False

    def test_toggle_builtin_node(self, mock_client):
        resp = MagicMock()
        resp.ok = True
        mock_client.post_data.return_value = resp

        result = toggle_offline(mock_client, "built-in", msg="Going offline")

        assert result is True
        mock_client.post_data.assert_called_once_with(
            "/computer/built-in/toggleOffline",
            data={"offlineMessage": "Going offline"},
        )


# ==================================================================
# create_node tests
# ==================================================================


class TestCreateNode:
    def test_create_node_defaults(self, mock_client):
        resp = MagicMock()
        resp.ok = True
        mock_client.request.return_value = resp

        result = create_node(mock_client, "agent-2")

        assert result is resp
        mock_client.request.assert_called_once()
        call_args = mock_client.request.call_args
        assert call_args[0] == ("POST", "/computer/doCreateItem")
        assert call_args[1]["params"] == {"name": "agent-2", "type": "hudson.slaves.DumbSlave"}
        data_sent = call_args[1]["data"]
        assert data_sent["name"] == "agent-2"
        assert data_sent["type"] == "hudson.slaves.DumbSlave"
        json_data = __import__("json").loads(data_sent["json"])
        assert json_data["name"] == "agent-2"
        assert json_data["numExecutors"] == "1"
        assert json_data["remoteFS"] == "/tmp"
        assert json_data["labelString"] == ""

    def test_create_node_with_custom_params(self, mock_client):
        resp = MagicMock()
        resp.ok = True
        mock_client.request.return_value = resp

        result = create_node(mock_client, "agent-3", num_executors=4,
                             remote_fs="/data/jenkins", labels="linux docker")

        json_data = __import__("json").loads(
            mock_client.request.call_args[1]["data"]["json"]
        )
        assert json_data["numExecutors"] == "4"
        assert json_data["remoteFS"] == "/data/jenkins"
        assert json_data["labelString"] == "linux docker"


# ==================================================================
# CLI tests — node
# ==================================================================

NODE_BASE_URL = "http://jenkins.example.com"


def _node_client() -> JenkinsClient:
    return JenkinsClient(NODE_BASE_URL, username="admin", token="fake-token")


class TestCLINodeList:
    @responses.activate
    def test_list_nodes_table(self) -> None:
        responses.add(
            responses.GET,
            f"{NODE_BASE_URL}/computer/api/json",
            json={
                "computer": [
                    {"displayName": "master", "offline": False, "temporarilyOffline": False, "numExecutors": 2,
                     "monitorData": {"hudson.node_monitors.ArchitectureMonitor": "Linux (amd64)"}},
                    {"displayName": "agent-1", "offline": True, "temporarilyOffline": True, "numExecutors": 4,
                     "monitorData": {"hudson.node_monitors.ArchitectureMonitor": "Linux (amd64)"}},
                ]
            },
            status=200,
        )
        from jcli.plugins.node import node_group
        runner = CliRunner()
        result = runner.invoke(node_group, ["list"], obj={"client": _node_client(), "format": "table"})
        assert result.exit_code == 0
        assert "master" in result.output
        assert "agent-1" in result.output

    @responses.activate
    def test_list_nodes_empty(self) -> None:
        responses.add(responses.GET, f"{NODE_BASE_URL}/computer/api/json", json={"computer": []}, status=200)
        from jcli.plugins.node import node_group
        runner = CliRunner()
        result = runner.invoke(node_group, ["list"], obj={"client": _node_client(), "format": "table"})
        assert result.exit_code == 0
        assert "No nodes found" in result.output


class TestCLINodeGet:
    @responses.activate
    def test_get_node_table(self) -> None:
        responses.add(
            responses.GET,
            f"{NODE_BASE_URL}/computer/agent-1/api/json",
            json={"displayName": "agent-1", "description": "Build agent", "offline": False,
                  "temporarilyOffline": False, "numExecutors": 4, "idle": True, "jnlpAgent": True, "monitorData": {}},
            status=200,
        )
        from jcli.plugins.node import node_group
        runner = CliRunner()
        result = runner.invoke(node_group, ["get", "agent-1"], obj={"client": _node_client(), "format": "table"})
        assert result.exit_code == 0
        assert "agent-1" in result.output
        assert "4" in result.output

    @responses.activate
    def test_get_node_json(self) -> None:
        responses.add(
            responses.GET,
            f"{NODE_BASE_URL}/computer/agent-1/api/json",
            json={"displayName": "agent-1", "offline": False, "numExecutors": 4},
            status=200,
        )
        from jcli.plugins.node import node_group
        runner = CliRunner()
        result = runner.invoke(node_group, ["get", "agent-1"], obj={"client": _node_client(), "format": "json"})
        assert result.exit_code == 0
        parsed = __import__("json").loads(result.output)
        assert parsed["displayName"] == "agent-1"


class TestCLINodeDelete:
    @responses.activate
    def test_delete_without_force_prompts(self) -> None:
        from jcli.plugins.node import node_group
        runner = CliRunner()
        result = runner.invoke(node_group, ["delete", "old-agent"], input="n\n", obj={"client": _node_client(), "format": "table"})
        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()

    @responses.activate
    def test_delete_with_force_flag(self) -> None:
        responses.add(responses.GET, f"{NODE_BASE_URL}/crumbIssuer/api/json",
                       json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"}, status=200)
        responses.add(responses.POST, f"{NODE_BASE_URL}/computer/old-agent/doDelete", status=200)
        from jcli.plugins.node import node_group
        runner = CliRunner()
        result = runner.invoke(node_group, ["delete", "old-agent", "--force"], obj={"client": _node_client(), "format": "table"})
        assert result.exit_code == 0
        assert "deleted" in result.output.lower()


class TestCLINodeToggle:
    @responses.activate
    def test_toggle_node(self) -> None:
        responses.add(responses.GET, f"{NODE_BASE_URL}/crumbIssuer/api/json",
                       json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"}, status=200)
        responses.add(responses.POST, f"{NODE_BASE_URL}/computer/agent-1/toggleOffline", status=200)
        from jcli.plugins.node import node_group
        runner = CliRunner()
        result = runner.invoke(node_group, ["toggle", "agent-1"], obj={"client": _node_client(), "format": "table"})
        assert result.exit_code == 0
        assert "toggled" in result.output.lower()

    @responses.activate
    def test_toggle_node_with_message(self) -> None:
        responses.add(responses.GET, f"{NODE_BASE_URL}/crumbIssuer/api/json",
                       json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"}, status=200)
        responses.add(responses.POST, f"{NODE_BASE_URL}/computer/agent-1/toggleOffline", status=200)
        from jcli.plugins.node import node_group
        runner = CliRunner()
        result = runner.invoke(node_group, ["toggle", "agent-1", "--message", "Maintenance"], obj={"client": _node_client(), "format": "table"})
        assert result.exit_code == 0
        assert "toggled" in result.output.lower()


class TestCLINodeCreate:
    @responses.activate
    def test_create_node(self) -> None:
        responses.add(responses.GET, f"{NODE_BASE_URL}/crumbIssuer/api/json",
                       json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"}, status=200)
        responses.add(responses.POST, f"{NODE_BASE_URL}/computer/doCreateItem", status=200)
        from jcli.plugins.node import node_group
        runner = CliRunner()
        result = runner.invoke(node_group, ["create", "agent-2"], obj={"client": _node_client(), "format": "table"})
        assert result.exit_code == 0
        assert "created" in result.output.lower()

    @responses.activate
    def test_create_node_with_options(self) -> None:
        responses.add(responses.GET, f"{NODE_BASE_URL}/crumbIssuer/api/json",
                       json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"}, status=200)
        responses.add(responses.POST, f"{NODE_BASE_URL}/computer/doCreateItem", status=200)
        from jcli.plugins.node import node_group
        runner = CliRunner()
        result = runner.invoke(
            node_group,
            ["create", "agent-3", "--executors", "4", "--remote-fs", "/data", "--labels", "linux"],
            obj={"client": _node_client(), "format": "table"},
        )
        assert result.exit_code == 0
        assert "created" in result.output.lower()

    def test_create_help(self) -> None:
        from jcli.plugins.node import node_group
        runner = CliRunner()
        result = runner.invoke(node_group, ["create", "--help"])
        assert result.exit_code == 0
        assert "Create a new Jenkins agent node" in result.output
        assert "--executors" in result.output
        assert "--remote-fs" in result.output
        assert "--labels" in result.output
