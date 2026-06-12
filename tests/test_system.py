"""Tests for jcli.sdk.system — Jenkins System SDK functions and CLI."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import responses
from click.testing import CliRunner

from jcli.sdk.exceptions import JenkinsAPIError, JenkinsAuthError, JenkinsNotFoundError
from jcli.sdk.system import (
    cancel_quiet_down,
    generate_token,
    get_system_info,
    get_system_load,
    list_users,
    quiet_down,
    run_script,
    safe_restart,
)

BASE_URL = "http://jenkins.example.com"

# Sample API responses
SYSTEM_INFO_RESPONSE = {
    "_class": "hudson.model.Hudson",
    "numExecutors": 2,
    "mode": "NORMAL",
    "quietingDown": False,
    "slaveAgentPort": 50000,
    "computer": [
        {
            "displayName": "built-in",
            "numExecutors": 2,
            "offline": False,
        },
        {
            "displayName": "agent-1",
            "numExecutors": 4,
            "offline": False,
        },
    ],
    "jobs": [
        {"name": "job-1", "url": "http://jenkins/job/job-1/", "color": "blue"},
        {"name": "job-2", "url": "http://jenkins/job/job-2/", "color": "red"},
        {"name": "job-3", "url": "http://jenkins/job/job-3/", "color": "blue_anime"},
    ],
}

QUEUE_RESPONSE = {
    "_class": "hudson.model.Queue",
    "items": [
        {"id": 1, "task": {"name": "job-2"}},
        {"id": 2, "task": {"name": "job-1"}},
    ],
}

COMPUTER_RESPONSE = {
    "_class": "hudson.model.ComputerSet",
    "computer": [
        {
            "displayName": "built-in",
            "numExecutors": 2,
            "busyExecutors": 1,
            "offline": False,
        },
        {
            "displayName": "agent-1",
            "numExecutors": 4,
            "busyExecutors": 2,
            "offline": False,
        },
    ],
}


# ==================================================================
# get_system_info
# ==================================================================


class TestGetSystemInfo:
    @responses.activate
    def test_basic_info(self, jenkins_client):
        """get_system_info returns version, nodes, jobs from API."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json",
            json=SYSTEM_INFO_RESPONSE,
            status=200,
            headers={"X-Jenkins": "2.440.1"},
        )

        info = get_system_info(jenkins_client)

        assert info["version"] == "2.440.1"
        assert info["num_executors"] == 2
        assert info["mode"] == "NORMAL"
        assert info["quietingDown"] is False
        assert info["slaveAgentPort"] == 50000
        assert info["num_nodes"] == 2
        assert info["num_jobs"] == 3
        assert info["raw"] == SYSTEM_INFO_RESPONSE

    @responses.activate
    def test_version_unknown_when_header_missing(self, jenkins_client):
        """When X-Jenkins header is missing, version defaults to 'unknown'."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json",
            json=SYSTEM_INFO_RESPONSE,
            status=200,
            # No X-Jenkins header
        )

        info = get_system_info(jenkins_client)

        assert info["version"] == "unknown"

    @responses.activate
    def test_no_computer_key(self, jenkins_client):
        """When 'computer' key is absent, num_nodes is 0."""
        data_without_computer = dict(SYSTEM_INFO_RESPONSE)
        del data_without_computer["computer"]

        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json",
            json=data_without_computer,
            status=200,
            headers={"X-Jenkins": "2.440.1"},
        )

        info = get_system_info(jenkins_client)

        assert info["num_nodes"] == 0

    @responses.activate
    def test_no_jobs_key(self, jenkins_client):
        """When 'jobs' key is absent, num_jobs is 0."""
        data_without_jobs = dict(SYSTEM_INFO_RESPONSE)
        del data_without_jobs["jobs"]

        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json",
            json=data_without_jobs,
            status=200,
            headers={"X-Jenkins": "2.440.1"},
        )

        info = get_system_info(jenkins_client)

        assert info["num_jobs"] == 0

    @responses.activate
    def test_quieting_down_true(self, jenkins_client):
        """quietingDown flag is correctly returned."""
        data = dict(SYSTEM_INFO_RESPONSE)
        data["quietingDown"] = True

        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json",
            json=data,
            status=200,
            headers={"X-Jenkins": "2.440.1"},
        )

        info = get_system_info(jenkins_client)

        assert info["quietingDown"] is True


# ==================================================================
# safe_restart
# ==================================================================


class TestSafeRestart:
    @responses.activate
    def test_success(self, jenkins_client_with_crumb):
        """safe_restart returns True on 200."""
        responses.add(
            responses.POST,
            f"{BASE_URL}/safeRestart",
            status=200,
        )

        result = safe_restart(jenkins_client_with_crumb)

        assert result is True

    @responses.activate
    def test_redirect_success(self, jenkins_client_with_crumb):
        """safe_restart returns True on 302 (redirect after POST)."""
        responses.add(
            responses.POST,
            f"{BASE_URL}/safeRestart",
            status=302,
        )

        result = safe_restart(jenkins_client_with_crumb)

        assert result is True

    @responses.activate
    def test_403_raises_api_error(self, jenkins_client_with_crumb):
        """safe_restart raises JenkinsAPIError on 403 Forbidden."""
        responses.add(
            responses.POST,
            f"{BASE_URL}/safeRestart",
            status=403,
        )

        with pytest.raises(JenkinsAPIError) as exc_info:
            safe_restart(jenkins_client_with_crumb)

        assert exc_info.value.status_code == 403


# ==================================================================
# quiet_down
# ==================================================================


class TestQuietDown:
    @responses.activate
    def test_success_no_reason(self, jenkins_client_with_crumb):
        """quiet_down without reason returns True on 200."""
        responses.add(
            responses.POST,
            f"{BASE_URL}/quietDown",
            status=200,
        )

        result = quiet_down(jenkins_client_with_crumb)

        assert result is True

    @responses.activate
    def test_success_with_reason(self, jenkins_client_with_crumb):
        """quiet_down with reason passes it as query param."""
        responses.add(
            responses.POST,
            f"{BASE_URL}/quietDown?reason=maintenance",
            status=200,
        )

        result = quiet_down(jenkins_client_with_crumb, reason="maintenance")

        assert result is True

    @responses.activate
    def test_empty_reason_not_sent(self, jenkins_client_with_crumb):
        """Empty reason string does not add query param."""
        responses.add(
            responses.POST,
            f"{BASE_URL}/quietDown",
            status=200,
        )

        result = quiet_down(jenkins_client_with_crumb, reason="")

        assert result is True
        # Verify no 'reason' in URL query
        url = responses.calls[0].request.url
        assert "reason" not in (url.split("?")[1] if "?" in url else "")

    @responses.activate
    def test_redirect_success(self, jenkins_client_with_crumb):
        """quiet_down returns True on 302."""
        responses.add(
            responses.POST,
            f"{BASE_URL}/quietDown",
            status=302,
        )

        result = quiet_down(jenkins_client_with_crumb)

        assert result is True


# ==================================================================
# cancel_quiet_down
# ==================================================================


class TestCancelQuietDown:
    @responses.activate
    def test_success(self, jenkins_client_with_crumb):
        """cancel_quiet_down returns True on 200."""
        responses.add(
            responses.POST,
            f"{BASE_URL}/cancelQuietDown",
            status=200,
        )

        result = cancel_quiet_down(jenkins_client_with_crumb)

        assert result is True

    @responses.activate
    def test_redirect_success(self, jenkins_client_with_crumb):
        """cancel_quiet_down returns True on 302."""
        responses.add(
            responses.POST,
            f"{BASE_URL}/cancelQuietDown",
            status=302,
        )

        result = cancel_quiet_down(jenkins_client_with_crumb)

        assert result is True


# ==================================================================
# get_system_load
# ==================================================================


class TestGetSystemLoad:
    @responses.activate
    def test_load_with_queue_and_executors(self, jenkins_client):
        """get_system_load returns queue length and executor stats."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/queue/api/json",
            json=QUEUE_RESPONSE,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/computer/api/json",
            json=COMPUTER_RESPONSE,
            status=200,
        )

        load = get_system_load(jenkins_client)

        assert load["queue_length"] == 2
        assert load["total_executors"] == 6  # 2 + 4
        assert load["busy_executors"] == 3  # 1 + 2
        assert load["idle_executors"] == 3  # 6 - 3

    @responses.activate
    def test_empty_queue(self, jenkins_client):
        """get_system_load reports 0 when queue is empty."""
        empty_queue = {"_class": "hudson.model.Queue", "items": []}

        responses.add(
            responses.GET,
            f"{BASE_URL}/queue/api/json",
            json=empty_queue,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/computer/api/json",
            json=COMPUTER_RESPONSE,
            status=200,
        )

        load = get_system_load(jenkins_client)

        assert load["queue_length"] == 0

    @responses.activate
    def test_queue_items_is_null(self, jenkins_client):
        """When 'items' key is missing, queue_length is 0."""
        empty_queue = {"_class": "hudson.model.Queue"}

        responses.add(
            responses.GET,
            f"{BASE_URL}/queue/api/json",
            json=empty_queue,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/computer/api/json",
            json=COMPUTER_RESPONSE,
            status=200,
        )

        load = get_system_load(jenkins_client)

        assert load["queue_length"] == 0

    @responses.activate
    def test_all_executors_idle(self, jenkins_client):
        """When no busy executors, idle equals total."""
        idle_computers = {
            "_class": "hudson.model.ComputerSet",
            "computer": [
                {
                    "displayName": "built-in",
                    "numExecutors": 2,
                    "busyExecutors": 0,
                    "offline": False,
                },
            ],
        }

        responses.add(
            responses.GET,
            f"{BASE_URL}/queue/api/json",
            json={"items": []},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/computer/api/json",
            json=idle_computers,
            status=200,
        )

        load = get_system_load(jenkins_client)

        assert load["idle_executors"] == 2
        assert load["busy_executors"] == 0


# ==================================================================
# CLI tests — system
# ==================================================================


SYS_BASE_URL = BASE_URL


class TestCLISystemInfo:
    @responses.activate
    @patch("jcli.plugins.system.Config.load", return_value=None)
    @patch("jcli.plugins.system.Config.get_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    @patch("jcli.plugins.system.Config.get_active_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    def test_info_output(self, mock_gap, mock_gp, mock_load) -> None:
        responses.add(responses.GET, f"{SYS_BASE_URL}/api/json",
                       json={"_class": "hudson.model.Hudson", "numExecutors": 4, "mode": "NORMAL",
                              "quietingDown": False, "slaveAgentPort": 50000,
                              "computer": [{"displayName": "built-in", "numExecutors": 4}],
                              "jobs": [{"name": "job1"}]},
                       status=200, headers={"X-Jenkins": "2.440.1"})

        from jcli.plugins.system import system_group
        runner = CliRunner()
        result = runner.invoke(system_group, ["info"], obj={"format": "table"})
        assert result.exit_code == 0
        assert "2.440.1" in result.output


class TestCLISystemRestart:
    @responses.activate
    @patch("jcli.plugins.system.Config.load", return_value=None)
    @patch("jcli.plugins.system.Config.get_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    @patch("jcli.plugins.system.Config.get_active_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    def test_restart_success(self, mock_gap, mock_gp, mock_load) -> None:
        responses.add(responses.GET, f"{SYS_BASE_URL}/crumbIssuer/api/json",
                       json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"}, status=200)
        responses.add(responses.POST, f"{SYS_BASE_URL}/safeRestart", status=200)

        from jcli.plugins.system import system_group
        runner = CliRunner()
        result = runner.invoke(system_group, ["restart"], obj={"format": "table"})
        assert result.exit_code == 0
        assert "restart" in result.output.lower()


class TestCLISystemQuietDown:
    @responses.activate
    @patch("jcli.plugins.system.Config.load", return_value=None)
    @patch("jcli.plugins.system.Config.get_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    @patch("jcli.plugins.system.Config.get_active_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    def test_quiet_down_success(self, mock_gap, mock_gp, mock_load) -> None:
        responses.add(responses.GET, f"{SYS_BASE_URL}/crumbIssuer/api/json",
                       json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"}, status=200)
        responses.add(responses.POST, f"{SYS_BASE_URL}/quietDown", status=200)

        from jcli.plugins.system import system_group
        runner = CliRunner()
        result = runner.invoke(system_group, ["quiet-down"], obj={"format": "table"})
        assert result.exit_code == 0
        assert "quiet-down" in result.output.lower()

    @responses.activate
    @patch("jcli.plugins.system.Config.load", return_value=None)
    @patch("jcli.plugins.system.Config.get_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    @patch("jcli.plugins.system.Config.get_active_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    def test_quiet_down_with_reason(self, mock_gap, mock_gp, mock_load) -> None:
        responses.add(responses.GET, f"{SYS_BASE_URL}/crumbIssuer/api/json",
                       json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"}, status=200)
        responses.add(responses.POST, f"{SYS_BASE_URL}/quietDown?reason=maintenance", status=200)

        from jcli.plugins.system import system_group
        runner = CliRunner()
        result = runner.invoke(system_group, ["quiet-down", "--reason", "maintenance"], obj={"format": "table"})
        assert result.exit_code == 0


class TestCLISystemCancelQuietDown:
    @responses.activate
    @patch("jcli.plugins.system.Config.load", return_value=None)
    @patch("jcli.plugins.system.Config.get_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    @patch("jcli.plugins.system.Config.get_active_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    def test_cancel_quiet_down(self, mock_gap, mock_gp, mock_load) -> None:
        responses.add(responses.GET, f"{SYS_BASE_URL}/crumbIssuer/api/json",
                       json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"}, status=200)
        responses.add(responses.POST, f"{SYS_BASE_URL}/cancelQuietDown", status=200)

        from jcli.plugins.system import system_group
        runner = CliRunner()
        result = runner.invoke(system_group, ["cancel-quiet-down"], obj={"format": "table"})
        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()


class TestCLISystemLoad:
    @responses.activate
    @patch("jcli.plugins.system.Config.load", return_value=None)
    @patch("jcli.plugins.system.Config.get_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    @patch("jcli.plugins.system.Config.get_active_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    def test_load_output(self, mock_gap, mock_gp, mock_load) -> None:
        responses.add(responses.GET, f"{SYS_BASE_URL}/queue/api/json",
                       json={"items": [{"id": 1, "task": {"name": "job1"}}]}, status=200)
        responses.add(responses.GET, f"{SYS_BASE_URL}/computer/api/json",
                       json={"computer": [{"numExecutors": 2, "busyExecutors": 1, "offline": False},
                                           {"numExecutors": 4, "busyExecutors": 0, "offline": False}]}, status=200)

        from jcli.plugins.system import system_group
        runner = CliRunner()
        result = runner.invoke(system_group, ["load"], obj={"format": "table"})
        assert result.exit_code == 0
        assert "1" in result.output


# ==================================================================
# run_script
# ==================================================================


class TestRunScript:
    @responses.activate
    def test_success(self, jenkins_client_with_crumb):
        """run_script returns the script output text."""
        responses.add(
            responses.POST,
            f"{BASE_URL}/scriptText",
            body="Hello from Groovy!",
            status=200,
        )

        result = run_script(jenkins_client_with_crumb, 'println("Hello")')

        assert result == "Hello from Groovy!"

    @responses.activate
    def test_auth_error(self, jenkins_client_with_crumb):
        """run_script raises JenkinsAuthError on 401."""
        responses.add(
            responses.POST,
            f"{BASE_URL}/scriptText",
            status=401,
        )

        with pytest.raises(JenkinsAuthError):
            run_script(jenkins_client_with_crumb, 'println("hi")')


# ==================================================================
# CLI tests — system script
# ==================================================================


class TestCLISystemScript:
    @responses.activate
    @patch("jcli.plugins.system.Config.load", return_value=None)
    @patch("jcli.plugins.system.Config.get_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    @patch("jcli.plugins.system.Config.get_active_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    def test_script_output(self, mock_gap, mock_gp, mock_load) -> None:
        responses.add(responses.GET, f"{SYS_BASE_URL}/crumbIssuer/api/json",
                       json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"}, status=200)
        responses.add(responses.POST, f"{SYS_BASE_URL}/scriptText",
                       body="Hello from Groovy!", status=200)

        from jcli.plugins.system import system_group
        runner = CliRunner()
        result = runner.invoke(system_group, ["script", 'println("Hello")'],
                               obj={"format": "table"})
        assert result.exit_code == 0
        assert "Hello from Groovy!" in result.output

    @responses.activate
    @patch("jcli.plugins.system.Config.load", return_value=None)
    @patch("jcli.plugins.system.Config.get_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    @patch("jcli.plugins.system.Config.get_active_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    def test_script_auth_error(self, mock_gap, mock_gp, mock_load) -> None:
        responses.add(responses.GET, f"{SYS_BASE_URL}/crumbIssuer/api/json",
                       json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"}, status=200)
        responses.add(responses.POST, f"{SYS_BASE_URL}/scriptText", status=401)

        from jcli.plugins.system import system_group
        runner = CliRunner()
        result = runner.invoke(system_group, ["script", 'println("hi")'],
                               obj={"format": "table"})
        # CLI handles the error gracefully, error is printed but exit code may still be 0
        assert "Authentication failed" in result.output


# ==================================================================
# Sample responses for users / token
# ==================================================================

USERS_RESPONSE = {
    "_class": "hudson.model.View$AsynchPeoplePeople",
    "users": [
        {
            "user": {
                "fullName": "admin",
                "absoluteUrl": "http://jenkins.example.com/user/admin",
            }
        },
        {
            "user": {
                "fullName": "developer",
                "description": "Lead Developer",
                "absoluteUrl": "http://jenkins.example.com/user/developer",
            }
        },
    ],
}

TOKEN_RESPONSE = {
    "status": "ok",
    "data": {
        "tokenName": "jcli-generated",
        "tokenUuid": "abc-123-uuid",
        "tokenValue": "110abcdef0123456789abcdef0123456789ab",
    },
}

TOKEN_ERROR_RESPONSE = "User not found: nobody"


# ==================================================================
# list_users
# ==================================================================


class TestListUsers:
    @responses.activate
    def test_success(self, jenkins_client):
        """list_users returns parsed JSON from /asynchPeople/api/json."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/asynchPeople/api/json",
            json=USERS_RESPONSE,
            status=200,
        )

        data = list_users(jenkins_client)

        assert data == USERS_RESPONSE
        assert len(data["users"]) == 2

    @responses.activate
    def test_empty_users(self, jenkins_client):
        """list_users handles empty users list."""
        empty = {"_class": "hudson.model.View$AsynchPeoplePeople", "users": []}

        responses.add(
            responses.GET,
            f"{BASE_URL}/asynchPeople/api/json",
            json=empty,
            status=200,
        )

        data = list_users(jenkins_client)

        assert data["users"] == []

    @responses.activate
    def test_auth_error(self, jenkins_client):
        """list_users raises JenkinsAuthError on 401."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/asynchPeople/api/json",
            status=401,
        )

        with pytest.raises(JenkinsAuthError):
            list_users(jenkins_client)


# ==================================================================
# generate_token
# ==================================================================


class TestGenerateToken:
    @responses.activate
    def test_success(self, jenkins_client_with_crumb):
        """generate_token returns token data on success."""
        responses.add(
            responses.POST,
            f"{BASE_URL}/user/admin/descriptorByName/jenkins.security.ApiTokenProperty/generateNewToken",
            json=TOKEN_RESPONSE,
            status=200,
        )

        result = generate_token(jenkins_client_with_crumb, "admin")

        assert result == TOKEN_RESPONSE
        assert result["data"]["tokenValue"] == "110abcdef0123456789abcdef0123456789ab"

    @responses.activate
    def test_custom_token_name(self, jenkins_client_with_crumb):
        """generate_token passes custom token_name in form data."""
        responses.add(
            responses.POST,
            f"{BASE_URL}/user/developer/descriptorByName/jenkins.security.ApiTokenProperty/generateNewToken",
            json=TOKEN_RESPONSE,
            status=200,
        )

        result = generate_token(jenkins_client_with_crumb, "developer", token_name="my-token")

        assert result == TOKEN_RESPONSE

    @responses.activate
    def test_user_not_found(self, jenkins_client_with_crumb):
        """generate_token raises JenkinsNotFoundError on 404."""
        responses.add(
            responses.POST,
            f"{BASE_URL}/user/nobody/descriptorByName/jenkins.security.ApiTokenProperty/generateNewToken",
            status=404,
        )

        with pytest.raises(JenkinsNotFoundError):
            generate_token(jenkins_client_with_crumb, "nobody")

    @responses.activate
    def test_auth_error(self, jenkins_client_with_crumb):
        """generate_token raises JenkinsAuthError on 401."""
        responses.add(
            responses.POST,
            f"{BASE_URL}/user/admin/descriptorByName/jenkins.security.ApiTokenProperty/generateNewToken",
            status=401,
        )

        with pytest.raises(JenkinsAuthError):
            generate_token(jenkins_client_with_crumb, "admin")


# ==================================================================
# CLI tests — system users
# ==================================================================


class TestCLISystemUsers:
    @responses.activate
    @patch("jcli.plugins.system.Config.load", return_value=None)
    @patch("jcli.plugins.system.Config.get_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    @patch("jcli.plugins.system.Config.get_active_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    def test_users_output(self, mock_gap, mock_gp, mock_load) -> None:
        responses.add(
            responses.GET,
            f"{SYS_BASE_URL}/asynchPeople/api/json",
            json=USERS_RESPONSE,
            status=200,
        )

        from jcli.plugins.system import system_group
        runner = CliRunner()
        result = runner.invoke(system_group, ["users"], obj={"format": "json"})
        assert result.exit_code == 0
        assert "admin" in result.output
        assert "developer" in result.output

    @responses.activate
    @patch("jcli.plugins.system.Config.load", return_value=None)
    @patch("jcli.plugins.system.Config.get_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    @patch("jcli.plugins.system.Config.get_active_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    def test_users_empty(self, mock_gap, mock_gp, mock_load) -> None:
        responses.add(
            responses.GET,
            f"{SYS_BASE_URL}/asynchPeople/api/json",
            json={"users": []},
            status=200,
        )

        from jcli.plugins.system import system_group
        runner = CliRunner()
        result = runner.invoke(system_group, ["users"], obj={"format": "table"})
        assert result.exit_code == 0
        assert "No users" in result.output

    @responses.activate
    @patch("jcli.plugins.system.Config.load", return_value=None)
    @patch("jcli.plugins.system.Config.get_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    @patch("jcli.plugins.system.Config.get_active_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    def test_users_auth_error(self, mock_gap, mock_gp, mock_load) -> None:
        responses.add(
            responses.GET,
            f"{SYS_BASE_URL}/asynchPeople/api/json",
            status=401,
        )

        from jcli.plugins.system import system_group
        runner = CliRunner()
        result = runner.invoke(system_group, ["users"], obj={"format": "table"})
        assert "Authentication failed" in result.output


# ==================================================================
# CLI tests — system token
# ==================================================================


class TestCLISystemToken:
    @responses.activate
    @patch("jcli.plugins.system.Config.load", return_value=None)
    @patch("jcli.plugins.system.Config.get_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    @patch("jcli.plugins.system.Config.get_active_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    def test_token_success(self, mock_gap, mock_gp, mock_load) -> None:
        responses.add(responses.GET, f"{SYS_BASE_URL}/crumbIssuer/api/json",
                       json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"}, status=200)
        responses.add(
            responses.POST,
            f"{SYS_BASE_URL}/user/admin/descriptorByName/jenkins.security.ApiTokenProperty/generateNewToken",
            json=TOKEN_RESPONSE,
            status=200,
        )

        from jcli.plugins.system import system_group
        runner = CliRunner()
        result = runner.invoke(system_group, ["token", "admin"], obj={"format": "json"})
        assert result.exit_code == 0
        assert "jcli-generated" in result.output
        assert "Token generated" in result.output

    @responses.activate
    @patch("jcli.plugins.system.Config.load", return_value=None)
    @patch("jcli.plugins.system.Config.get_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    @patch("jcli.plugins.system.Config.get_active_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    def test_token_custom_name(self, mock_gap, mock_gp, mock_load) -> None:
        responses.add(responses.GET, f"{SYS_BASE_URL}/crumbIssuer/api/json",
                       json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"}, status=200)
        responses.add(
            responses.POST,
            f"{SYS_BASE_URL}/user/admin/descriptorByName/jenkins.security.ApiTokenProperty/generateNewToken",
            json=TOKEN_RESPONSE,
            status=200,
        )

        from jcli.plugins.system import system_group
        runner = CliRunner()
        result = runner.invoke(system_group, ["token", "admin", "--name", "my-token"], obj={"format": "json"})
        assert result.exit_code == 0

    @responses.activate
    @patch("jcli.plugins.system.Config.load", return_value=None)
    @patch("jcli.plugins.system.Config.get_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    @patch("jcli.plugins.system.Config.get_active_profile", return_value={"url": SYS_BASE_URL, "username": "admin", "api_token": "fake-token"})
    def test_token_error(self, mock_gap, mock_gp, mock_load) -> None:
        responses.add(responses.GET, f"{SYS_BASE_URL}/crumbIssuer/api/json",
                       json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"}, status=200)
        responses.add(
            responses.POST,
            f"{SYS_BASE_URL}/user/nobody/descriptorByName/jenkins.security.ApiTokenProperty/generateNewToken",
            status=404,
        )

        from jcli.plugins.system import system_group
        runner = CliRunner()
        result = runner.invoke(system_group, ["token", "nobody"], obj={"format": "table"})
        assert "not found" in result.output.lower()
