"""Tests for jcli.sdk.build — build and queue operations."""

from __future__ import annotations

import json

import pytest
import responses
from click.testing import CliRunner

from jcli.sdk.build import (
    _job_path,
    cancel_queue_item,
    get_build,
    get_build_artifacts,
    get_build_log,
    get_builds,
    get_queue,
    stop_build,
    trigger_build,
    wait_for_build,
)
from jcli.sdk.client import JenkinsClient

BASE_URL = "http://jenkins.example.com"
CRUMB_URL = f"{BASE_URL}/crumbIssuer/api/json"
CRUMB_RESPONSE = {"crumb": "abc123", "crumbRequestField": "Jenkins-Crumb"}


def _register_crumb(rsps: responses.RequestsMock) -> None:
    rsps.add(responses.GET, CRUMB_URL, json=CRUMB_RESPONSE, status=200)


def _mock_profile() -> dict:
    return {"url": BASE_URL, "username": "admin", "api_token": "fake-token"}


# ==================================================================
# _job_path
# ==================================================================


class TestJobPath:
    def test_simple_job(self) -> None:
        assert _job_path("my-job") == "/job/my-job"

    def test_nested_job(self) -> None:
        assert _job_path("folder/sub-job") == "/job/folder/job/sub-job"

    def test_deeply_nested(self) -> None:
        assert _job_path("a/b/c") == "/job/a/job/b/job/c"


# ==================================================================
# trigger_build
# ==================================================================


class TestTriggerBuild:
    @responses.activate
    def test_trigger_simple_build(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        # POST triggers build, returns Location header
        queue_url = f"{BASE_URL}/queue/item/42/"
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/test-job/build",
            status=201,
            headers={"Location": queue_url},
        )
        # GET the queue item
        responses.add(
            responses.GET,
            f"{BASE_URL}/queue/item/42/api/json",
            json={"id": 42, "task": {"name": "test-job"}, "why": "Started by user"},
            status=200,
        )

        result = trigger_build(jenkins_client, "test-job")
        assert result["id"] == 42
        assert result["task"]["name"] == "test-job"

    @responses.activate
    def test_trigger_with_parameters(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        queue_url = f"{BASE_URL}/queue/item/43/"
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/test-job/buildWithParameters",
            status=201,
            headers={"Location": queue_url},
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/queue/item/43/api/json",
            json={"id": 43, "params": '{"BRANCH": "main"}'},
            status=200,
        )

        result = trigger_build(jenkins_client, "test-job", params={"BRANCH": "main"})
        assert result["id"] == 43

    @responses.activate
    def test_trigger_nested_job(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        queue_url = f"{BASE_URL}/queue/item/44/"
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/folder/job/sub-job/build",
            status=201,
            headers={"Location": queue_url},
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/queue/item/44/api/json",
            json={"id": 44},
            status=200,
        )

        result = trigger_build(jenkins_client, "folder/sub-job")
        assert result["id"] == 44

    @responses.activate
    def test_trigger_queue_fetch_fails_gracefully(
        self, jenkins_client: JenkinsClient
    ) -> None:
        _register_crumb(responses)
        queue_url = f"{BASE_URL}/queue/item/45/"
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/test-job/build",
            status=201,
            headers={"Location": queue_url},
        )
        # Queue item GET returns 404
        responses.add(
            responses.GET,
            f"{BASE_URL}/queue/item/45/api/json",
            status=404,
        )

        result = trigger_build(jenkins_client, "test-job")
        # Falls back to minimal dict
        assert result["status"] == "queued"
        assert result["url"] == queue_url

    @responses.activate
    def test_trigger_no_location_header(
        self, jenkins_client: JenkinsClient
    ) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/test-job/build",
            status=200,
        )

        result = trigger_build(jenkins_client, "test-job")
        assert result["status"] == "queued"
        assert result["url"] == ""

    @responses.activate
    def test_trigger_params_in_url(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        queue_url = f"{BASE_URL}/queue/item/46/"
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/test-job/buildWithParameters",
            status=201,
            headers={"Location": queue_url},
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/queue/item/46/api/json",
            json={"id": 46},
            status=200,
        )

        result = trigger_build(
            jenkins_client,
            "test-job",
            params={"NAME": "value", "FLAG": "true"},
        )
        assert result["id"] == 46

        # Verify params were passed as query string
        req = responses.calls[1].request  # POST call (crumb call is [0])
        assert "NAME" in req.url
        assert "FLAG" in req.url


# ==================================================================
# get_build
# ==================================================================


class TestGetBuild:
    @responses.activate
    def test_get_build_success(self, jenkins_client: JenkinsClient) -> None:
        build_data = {
            "number": 1,
            "result": "SUCCESS",
            "duration": 12345,
            "building": False,
        }
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/1/api/json",
            json=build_data,
            status=200,
        )

        result = get_build(jenkins_client, "test-job", 1)
        assert result["number"] == 1
        assert result["result"] == "SUCCESS"

    @responses.activate
    def test_get_build_nested_job(self, jenkins_client: JenkinsClient) -> None:
        build_data = {"number": 5, "result": "FAILURE"}
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/folder/job/sub-job/5/api/json",
            json=build_data,
            status=200,
        )

        result = get_build(jenkins_client, "folder/sub-job", 5)
        assert result["number"] == 5
        assert result["result"] == "FAILURE"

    @responses.activate
    def test_get_build_not_found(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/999/api/json",
            status=404,
        )

        with pytest.raises(Exception):
            get_build(jenkins_client, "test-job", 999)


# ==================================================================
# get_builds
# ==================================================================


class TestGetBuilds:
    @responses.activate
    def test_get_builds_with_results(self, jenkins_client: JenkinsClient) -> None:
        builds_data = {
            "builds": [
                {"number": 3, "result": "SUCCESS", "building": False},
                {"number": 2, "result": "FAILURE", "building": False},
                {"number": 1, "result": "SUCCESS", "building": False},
            ]
        }
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/api/json",
            json=builds_data,
            status=200,
        )

        result = get_builds(jenkins_client, "test-job", limit=5)
        assert len(result) == 3
        assert result[0]["number"] == 3

    @responses.activate
    def test_get_builds_respects_limit(self, jenkins_client: JenkinsClient) -> None:
        builds_data = {
            "builds": [
                {"number": n, "result": "SUCCESS"} for n in range(10, 0, -1)
            ]
        }
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/api/json",
            json=builds_data,
            status=200,
        )

        result = get_builds(jenkins_client, "test-job", limit=3)
        assert len(result) == 3
        assert result[0]["number"] == 10
        assert result[2]["number"] == 8

    @responses.activate
    def test_get_builds_empty(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/api/json",
            json={"builds": []},
            status=200,
        )

        result = get_builds(jenkins_client, "test-job")
        assert result == []

    @responses.activate
    def test_get_builds_no_builds_key(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/api/json",
            json={"name": "test-job"},
            status=200,
        )

        result = get_builds(jenkins_client, "test-job")
        assert result == []


# ==================================================================
# get_build_log
# ==================================================================


class TestGetBuildLog:
    @responses.activate
    def test_get_build_log_full(self, jenkins_client: JenkinsClient) -> None:
        log_text = "Started by user admin\nBuilding...\nFinished: SUCCESS\n"
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/1/consoleText",
            body=log_text,
            status=200,
        )

        result = get_build_log(jenkins_client, "test-job", 1)
        assert result == log_text

    @responses.activate
    def test_get_build_log_with_offset(self, jenkins_client: JenkinsClient) -> None:
        log_text = "line1\nline2\nline3\n"
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/1/consoleText",
            body=log_text,
            status=200,
        )

        result = get_build_log(jenkins_client, "test-job", 1, start=6)
        assert result == "line2\nline3\n"

    @responses.activate
    def test_get_build_log_empty(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/1/consoleText",
            body="",
            status=200,
        )

        result = get_build_log(jenkins_client, "test-job", 1)
        assert result == ""

    @responses.activate
    def test_get_build_log_nested_job(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/folder/job/sub-job/2/consoleText",
            body="nested log",
            status=200,
        )

        result = get_build_log(jenkins_client, "folder/sub-job", 2)
        assert result == "nested log"


# ==================================================================
# stop_build
# ==================================================================


class TestStopBuild:
    @responses.activate
    def test_stop_build_success(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/test-job/1/stop",
            status=200,
        )

        result = stop_build(jenkins_client, "test-job", 1)
        assert result == {}

    @responses.activate
    def test_stop_nested_job(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/folder/job/sub-job/5/stop",
            status=200,
        )

        result = stop_build(jenkins_client, "folder/sub-job", 5)
        assert result == {}


# ==================================================================
# get_queue
# ==================================================================


class TestGetQueue:
    @responses.activate
    def test_get_queue_with_items(self, jenkins_client: JenkinsClient) -> None:
        queue_data = {
            "items": [
                {"id": 1, "task": {"name": "test-job"}, "why": "Waiting"},
                {"id": 2, "task": {"name": "other-job"}, "why": "Pending"},
            ]
        }
        responses.add(
            responses.GET,
            f"{BASE_URL}/queue/api/json",
            json=queue_data,
            status=200,
        )

        result = get_queue(jenkins_client)
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["task"]["name"] == "other-job"

    @responses.activate
    def test_get_queue_empty(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/queue/api/json",
            json={"items": []},
            status=200,
        )

        result = get_queue(jenkins_client)
        assert result == []

    @responses.activate
    def test_get_queue_no_items_key(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/queue/api/json",
            json={},
            status=200,
        )

        result = get_queue(jenkins_client)
        assert result == []


# ==================================================================
# cancel_queue_item
# ==================================================================


class TestCancelQueueItem:
    @responses.activate
    def test_cancel_queue_item_success(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/queue/cancelItem?id=42",
            status=200,
        )

        result = cancel_queue_item(jenkins_client, 42)
        assert result == {}

    @responses.activate
    def test_cancel_queue_item_not_found(self, jenkins_client: JenkinsClient) -> None:
        _register_crumb(responses)
        responses.add(
            responses.POST,
            f"{BASE_URL}/queue/cancelItem?id=999",
            status=404,
        )

        with pytest.raises(Exception):
            cancel_queue_item(jenkins_client, 999)


# ==================================================================
# wait_for_build
# ==================================================================


class TestWaitForBuild:
    @responses.activate
    def test_wait_completes_immediately(self, jenkins_client: JenkinsClient) -> None:
        """Build already finished — returns on first poll."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/1/api/json",
            json={"number": 1, "building": False, "result": "SUCCESS"},
            status=200,
        )

        result = wait_for_build(jenkins_client, "test-job", 1, timeout=30)
        assert result["building"] is False
        assert result["result"] == "SUCCESS"

    @responses.activate
    def test_wait_polls_until_complete(self, jenkins_client: JenkinsClient) -> None:
        """First poll returns building=True, second returns building=False."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/1/api/json",
            json={"number": 1, "building": True, "result": None},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/1/api/json",
            json={"number": 1, "building": False, "result": "SUCCESS"},
            status=200,
        )

        result = wait_for_build(
            jenkins_client, "test-job", 1, timeout=30, poll_interval=0.01
        )
        assert result["building"] is False
        assert result["result"] == "SUCCESS"
        assert len(responses.calls) == 2

    @responses.activate
    def test_wait_times_out(self, jenkins_client: JenkinsClient) -> None:
        """Build never finishes — timeout."""
        # Add many responses for polling loop
        for _ in range(50):
            responses.add(
                responses.GET,
                f"{BASE_URL}/job/test-job/1/api/json",
                json={"number": 1, "building": True, "result": None},
                status=200,
            )

        with pytest.raises(TimeoutError, match="did not complete"):
            wait_for_build(
                jenkins_client,
                "test-job",
                1,
                timeout=0.1,
                poll_interval=0.01,
            )

    @responses.activate
    def test_wait_with_custom_poll_interval(
        self, jenkins_client: JenkinsClient
    ) -> None:
        """Custom poll_interval parameter is respected."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/1/api/json",
            json={"number": 1, "building": False, "result": "ABORTED"},
            status=200,
        )

        result = wait_for_build(
            jenkins_client, "test-job", 1, timeout=30, poll_interval=5
        )
        assert result["result"] == "ABORTED"


# ==================================================================
# Integration tests with fixtures
# ==================================================================


class TestWithFixtures:
    @responses.activate
    def test_full_build_workflow(self, jenkins_client: JenkinsClient) -> None:
        """Simulate a complete build workflow: trigger → wait → get detail."""
        _register_crumb(responses)

        # 1. Trigger
        queue_url = f"{BASE_URL}/queue/item/100/"
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/test-job/build",
            status=201,
            headers={"Location": queue_url},
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/queue/item/100/api/json",
            json={"id": 100},
            status=200,
        )
        trigger_result = trigger_build(jenkins_client, "test-job")
        assert trigger_result["id"] == 100

        # 2. Get builds list
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/api/json",
            json={"builds": [{"number": 1, "result": None, "building": True}]},
            status=200,
        )
        builds = get_builds(jenkins_client, "test-job")
        assert len(builds) == 1
        assert builds[0]["building"] is True

        # 3. Get build detail
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/1/api/json",
            json={"number": 1, "result": "SUCCESS", "building": False},
            status=200,
        )
        build = get_build(jenkins_client, "test-job", 1)
        assert build["result"] == "SUCCESS"

        # 4. Get console log
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/1/consoleText",
            body="Build log here",
            status=200,
        )
        log = get_build_log(jenkins_client, "test-job", 1)
        assert log == "Build log here"


# ==================================================================
# CLI: build trigger
# ==================================================================

CLI_RUNNER = CliRunner()


def _build_client() -> JenkinsClient:
    return JenkinsClient(BASE_URL, username="admin", token="fake-token")


class TestCLIBuildTrigger:
    @responses.activate
    def test_trigger_build_table_output(self) -> None:
        _register_crumb(responses)
        queue_url = f"{BASE_URL}/queue/item/43/"
        responses.add(responses.POST, f"{BASE_URL}/job/my-build/build", status=201, headers={"Location": queue_url})
        responses.add(responses.GET, f"{BASE_URL}/queue/item/43/api/json", json={"id": 43, "task": {"name": "my-build"}}, status=200)

        from jcli.plugins.build import build_group
        result = CLI_RUNNER.invoke(build_group, ["trigger", "my-build"], obj={"client": _build_client(), "format": "table"})
        assert result.exit_code == 0
        assert "triggered" in result.output.lower()

    @responses.activate
    def test_trigger_with_params(self) -> None:
        _register_crumb(responses)
        queue_url = f"{BASE_URL}/queue/item/44/"
        responses.add(responses.POST, f"{BASE_URL}/job/test-job/buildWithParameters", status=201, headers={"Location": queue_url})
        responses.add(responses.GET, f"{BASE_URL}/queue/item/44/api/json", json={"id": 44}, status=200)

        from jcli.plugins.build import build_group
        result = CLI_RUNNER.invoke(build_group, ["trigger", "test-job", "--params", "BRANCH=main"], obj={"client": _build_client(), "format": "json"})
        assert result.exit_code == 0

    @responses.activate
    def test_trigger_bad_params_format(self) -> None:
        from jcli.plugins.build import build_group
        result = CLI_RUNNER.invoke(build_group, ["trigger", "test-job", "--params", "badparam"], obj={"client": _build_client(), "format": "table"})
        assert result.exit_code != 0


# ==================================================================
# CLI: build list
# ==================================================================


class TestCLIBuildList:
    @responses.activate
    def test_list_builds_table(self) -> None:
        data = {"builds": [{"number": 3, "result": "SUCCESS", "building": False}, {"number": 2, "result": "FAILURE", "building": False}]}
        responses.add(responses.GET, f"{BASE_URL}/job/test-job/api/json", json=data, status=200)

        from jcli.plugins.build import build_group
        result = CLI_RUNNER.invoke(build_group, ["list", "test-job"], obj={"client": _build_client(), "format": "table"})
        assert result.exit_code == 0
        assert "3" in result.output

    @responses.activate
    def test_list_builds_empty(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/job/empty-job/api/json", json={"builds": []}, status=200)

        from jcli.plugins.build import build_group
        result = CLI_RUNNER.invoke(build_group, ["list", "empty-job"], obj={"client": _build_client(), "format": "table"})
        assert result.exit_code == 0
        assert "No builds found" in result.output

    @responses.activate
    def test_list_builds_json(self) -> None:
        data = {"builds": [{"number": 1, "result": "SUCCESS", "building": False}]}
        responses.add(responses.GET, f"{BASE_URL}/job/test-job/api/json", json=data, status=200)

        from jcli.plugins.build import build_group
        result = CLI_RUNNER.invoke(build_group, ["list", "test-job"], obj={"client": _build_client(), "format": "json"})
        assert result.exit_code == 0
        assert "SUCCESS" in result.output


# ==================================================================
# CLI: build get
# ==================================================================


class TestCLIBuildGet:
    @responses.activate
    def test_get_build_details(self) -> None:
        build_data = {"number": 42, "result": "SUCCESS", "duration": 12345, "building": False}
        responses.add(responses.GET, f"{BASE_URL}/job/test-job/42/api/json", json=build_data, status=200)

        from jcli.plugins.build import build_group
        result = CLI_RUNNER.invoke(build_group, ["get", "test-job", "42"], obj={"client": _build_client(), "format": "json"})
        assert result.exit_code == 0
        assert "42" in result.output

    @responses.activate
    def test_get_build_not_found(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/job/test-job/999/api/json", status=404)

        from jcli.plugins.build import build_group
        result = CLI_RUNNER.invoke(build_group, ["get", "test-job", "999"], obj={"client": _build_client(), "format": "table"})
        assert result.exit_code != 0


# ==================================================================
# CLI: build log
# ==================================================================


class TestCLIBuildLog:
    @responses.activate
    def test_log_output(self) -> None:
        log_text = "Started by user admin\nBuilding...\nFinished: SUCCESS\n"
        responses.add(responses.GET, f"{BASE_URL}/job/test-job/1/consoleText", body=log_text, status=200)

        from jcli.plugins.build import build_group
        result = CLI_RUNNER.invoke(build_group, ["log", "test-job", "1"], obj={"client": _build_client(), "format": "table"})
        assert result.exit_code == 0
        assert "SUCCESS" in result.output


# ==================================================================
# CLI: build stop
# ==================================================================


class TestCLIBuildStop:
    @responses.activate
    def test_stop_build_success(self) -> None:
        _register_crumb(responses)
        responses.add(responses.POST, f"{BASE_URL}/job/test-job/1/stop", status=200)

        from jcli.plugins.build import build_group
        result = CLI_RUNNER.invoke(build_group, ["stop", "test-job", "1"], obj={"client": _build_client(), "format": "table"})
        assert result.exit_code == 0
        assert "stopped" in result.output.lower()


# ==================================================================
# CLI: build queue
# ==================================================================


class TestCLIBuildQueue:
    @responses.activate
    def test_queue_with_items(self) -> None:
        queue_data = {"items": [{"id": 1, "task": {"name": "test-job"}, "why": "Waiting"}]}
        responses.add(responses.GET, f"{BASE_URL}/queue/api/json", json=queue_data, status=200)

        from jcli.plugins.build import build_group
        result = CLI_RUNNER.invoke(build_group, ["queue"], obj={"client": _build_client(), "format": "table"})
        assert result.exit_code == 0
        assert "test-job" in result.output

    @responses.activate
    def test_queue_empty(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/queue/api/json", json={"items": []}, status=200)

        from jcli.plugins.build import build_group
        result = CLI_RUNNER.invoke(build_group, ["queue"], obj={"client": _build_client(), "format": "table"})
        assert result.exit_code == 0
        assert "empty" in result.output.lower()


# ==================================================================
# get_build_artifacts
# ==================================================================


class TestGetBuildArtifacts:
    @responses.activate
    def test_get_artifacts_with_data(self, jenkins_client: JenkinsClient) -> None:
        artifacts_data = {
            "artifacts": [
                {"fileName": "report.html", "relativePath": "report.html"},
                {"fileName": "app.jar", "relativePath": "target/app.jar"},
            ]
        }
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/1/api/json",
            json=artifacts_data,
            status=200,
        )

        result = get_build_artifacts(jenkins_client, "test-job", 1)
        assert len(result["artifacts"]) == 2
        assert result["artifacts"][0]["fileName"] == "report.html"
        assert result["artifacts"][1]["relativePath"] == "target/app.jar"

    @responses.activate
    def test_get_artifacts_empty(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/1/api/json",
            json={"artifacts": []},
            status=200,
        )

        result = get_build_artifacts(jenkins_client, "test-job", 1)
        assert result["artifacts"] == []

    @responses.activate
    def test_get_artifacts_nested_job(self, jenkins_client: JenkinsClient) -> None:
        artifacts_data = {
            "artifacts": [
                {"fileName": "output.zip", "relativePath": "dist/output.zip"},
            ]
        }
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/folder/job/sub-job/5/api/json",
            json=artifacts_data,
            status=200,
        )

        result = get_build_artifacts(jenkins_client, "folder/sub-job", 5)
        assert len(result["artifacts"]) == 1
        assert result["artifacts"][0]["fileName"] == "output.zip"


# ==================================================================
# CLI: build artifacts
# ==================================================================


class TestCLIBuildArtifacts:
    @responses.activate
    def test_artifacts_table_output(self) -> None:
        data = {
            "artifacts": [
                {"fileName": "report.html", "relativePath": "report.html"},
                {"fileName": "app.jar", "relativePath": "target/app.jar"},
            ]
        }
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/1/api/json",
            json=data,
            status=200,
        )

        from jcli.plugins.build import build_group
        result = CLI_RUNNER.invoke(
            build_group,
            ["artifacts", "test-job", "1"],
            obj={"client": _build_client(), "format": "table"},
        )
        assert result.exit_code == 0
        assert "report.html" in result.output
        assert "target/app.jar" in result.output

    @responses.activate
    def test_artifacts_empty(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/1/api/json",
            json={"artifacts": []},
            status=200,
        )

        from jcli.plugins.build import build_group
        result = CLI_RUNNER.invoke(
            build_group,
            ["artifacts", "test-job", "1"],
            obj={"client": _build_client(), "format": "table"},
        )
        assert result.exit_code == 0
        assert "No artifacts found" in result.output

    @responses.activate
    def test_artifacts_json_output(self) -> None:
        data = {
            "artifacts": [
                {"fileName": "output.zip", "relativePath": "dist/output.zip"},
            ]
        }
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/test-job/1/api/json",
            json=data,
            status=200,
        )

        from jcli.plugins.build import build_group
        result = CLI_RUNNER.invoke(
            build_group,
            ["artifacts", "test-job", "1"],
            obj={"client": _build_client(), "format": "json"},
        )
        assert result.exit_code == 0
        assert "output.zip" in result.output
