"""Tests for jcli.sdk.pipeline — Pipeline SDK functions and CLI."""

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
    JenkinsAuthError,
    JenkinsNotFoundError,
)
from jcli.sdk.pipeline import (
    get_pending_input,
    get_pipeline_log,
    get_pipeline_stages,
    validate_jenkinsfile,
)

BASE_URL = "http://jenkins.example.com"
JOB_NAME = "test-pipeline"
BUILD_NUMBER = 42


# ------------------------------------------------------------------
# Sample response data
# ------------------------------------------------------------------

SAMPLE_STAGES_RESPONSE = {
    "_links": {},
    "id": "42",
    "name": "#42",
    "status": "SUCCESS",
    "startTimeMillis": 1700000000000,
    "endTimeMillis": 1700000030000,
    "durationMillis": 30000,
    "stages": [
        {
            "id": "1",
            "name": "Build",
            "status": "SUCCESS",
            "startTimeMillis": 1700000001000,
            "durationMillis": 10000,
        },
        {
            "id": "2",
            "name": "Test",
            "status": "SUCCESS",
            "startTimeMillis": 1700000011000,
            "durationMillis": 15000,
        },
        {
            "id": "3",
            "name": "Deploy",
            "status": "SUCCESS",
            "startTimeMillis": 1700000026000,
            "durationMillis": 4000,
        },
    ],
}

SAMPLE_STAGES_FAILED = {
    "id": "43",
    "name": "#43",
    "status": "FAILED",
    "stages": [
        {"id": "1", "name": "Build", "status": "SUCCESS"},
        {"id": "2", "name": "Test", "status": "FAILED"},
        {"id": "3", "name": "Deploy", "status": "NOT_EXECUTED"},
    ],
}

SAMPLE_LOG_RESPONSE = {
    "nodeId": "7",
    "nodeStatus": "SUCCESS",
    "length": 512,
    "hasMore": False,
    "text": (
        "[Pipeline] node\n"
        "Running on agent-1 in /workspace\n"
        "[Pipeline] sh\n"
        "+ echo hello\n"
        "hello\n"
        "[Pipeline] }\n"
    ),
    "consoleUrl": "/job/test-pipeline/42/execution/node/7/log",
}

SAMPLE_VALIDATE_SUCCESS = {
    "result": "success",
    "data": {
        "result": "success",
        "errors": [],
    },
}

SAMPLE_VALIDATE_WITH_ERRORS = {
    "result": "failure",
    "data": {
        "result": "failure",
        "errors": [
            {
                "location": {"line": 5, "column": 1},
                "error": "Expected a step",
            }
        ],
    },
}

SAMPLE_PENDING_INPUT_ACTIONS = [
    {
        "id": "a1b2c3d4",
        "proceedUrl": "/job/test-pipeline/42/input/a1b2c3d4/proceed",
        "abortUrl": "/job/test-pipeline/42/input/a1b2c3d4/abort",
        "message": "Approve deployment?",
        "inputs": [
            {
                "id": "approved",
                "name": "approved",
                "type": "BooleanParameterDefinition",
                "description": "Check to approve",
            }
        ],
        "submitter": None,
        "submitterParameter": "submitter",
    }
]

SAMPLE_PENDING_EMPTY: list = []


# ------------------------------------------------------------------
# Helper: register mock URL
# ------------------------------------------------------------------

def _stages_url(job, build):
    return f"{BASE_URL}/job/{job}/{build}/wfapi/describe"


def _log_url(job, build, node):
    return f"{BASE_URL}/job/{job}/{build}/execution/node/{node}/wfapi/log"


_VALIDATE_URL = f"{BASE_URL}/pipeline-model-converter/validate"


def _pending_url(job, build):
    return f"{BASE_URL}/job/{job}/{build}/wfapi/pendingInputActions"


# ==================================================================
# get_pipeline_stages
# ==================================================================


class TestGetPipelineStages:
    @responses.activate
    def test_returns_stage_info(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _stages_url(JOB_NAME, BUILD_NUMBER),
            json=SAMPLE_STAGES_RESPONSE,
            status=200,
        )

        result = get_pipeline_stages(jenkins_client, JOB_NAME, BUILD_NUMBER)

        assert result["id"] == "42"
        assert result["status"] == "SUCCESS"
        assert len(result["stages"]) == 3
        assert result["stages"][0]["name"] == "Build"

    @responses.activate
    def test_failed_build(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _stages_url(JOB_NAME, 43),
            json=SAMPLE_STAGES_FAILED,
            status=200,
        )

        result = get_pipeline_stages(jenkins_client, JOB_NAME, 43)

        assert result["status"] == "FAILED"
        assert result["stages"][1]["status"] == "FAILED"

    @responses.activate
    def test_job_not_found(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _stages_url("nonexistent", 1),
            status=404,
        )

        with pytest.raises(JenkinsNotFoundError):
            get_pipeline_stages(jenkins_client, "nonexistent", 1)

    @responses.activate
    def test_build_number_as_int(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _stages_url(JOB_NAME, "99"),
            json=SAMPLE_STAGES_RESPONSE,
            status=200,
        )

        result = get_pipeline_stages(jenkins_client, JOB_NAME, 99)
        assert result["id"] == "42"

    @responses.activate
    def test_build_number_as_str(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _stages_url(JOB_NAME, "99"),
            json=SAMPLE_STAGES_RESPONSE,
            status=200,
        )

        result = get_pipeline_stages(jenkins_client, JOB_NAME, "99")
        assert result["status"] == "SUCCESS"


# ==================================================================
# get_pipeline_log
# ==================================================================


class TestGetPipelineLog:
    @responses.activate
    def test_returns_log_text(self, jenkins_client: JenkinsClient) -> None:
        node_id = 7
        responses.add(
            responses.GET,
            _log_url(JOB_NAME, BUILD_NUMBER, node_id),
            json=SAMPLE_LOG_RESPONSE,
            status=200,
        )

        result = get_pipeline_log(jenkins_client, JOB_NAME, BUILD_NUMBER, node_id)

        assert result["nodeId"] == "7"
        assert result["nodeStatus"] == "SUCCESS"
        assert "hello" in result["text"]
        assert result["hasMore"] is False

    @responses.activate
    def test_node_not_found(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _log_url(JOB_NAME, BUILD_NUMBER, 999),
            status=404,
        )

        with pytest.raises(JenkinsNotFoundError):
            get_pipeline_log(jenkins_client, JOB_NAME, BUILD_NUMBER, 999)

    @responses.activate
    def test_has_more_log(self, jenkins_client: JenkinsClient) -> None:
        truncated_log = dict(SAMPLE_LOG_RESPONSE, hasMore=True, text="truncated...")
        responses.add(
            responses.GET,
            _log_url(JOB_NAME, BUILD_NUMBER, 7),
            json=truncated_log,
            status=200,
        )

        result = get_pipeline_log(jenkins_client, JOB_NAME, BUILD_NUMBER, 7)
        assert result["hasMore"] is True
        assert result["text"] == "truncated..."

    @responses.activate
    def test_node_id_as_str(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _log_url(JOB_NAME, BUILD_NUMBER, "7"),
            json=SAMPLE_LOG_RESPONSE,
            status=200,
        )

        result = get_pipeline_log(jenkins_client, JOB_NAME, BUILD_NUMBER, "7")
        assert result["nodeStatus"] == "SUCCESS"


# ==================================================================
# validate_jenkinsfile
# ==================================================================


class TestValidateJenkinsfile:
    @responses.activate
    def test_valid_jenkinsfile(self, jenkins_client: JenkinsClient) -> None:
        # Crumb endpoint for POST
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        responses.add(
            responses.POST,
            _VALIDATE_URL,
            json=SAMPLE_VALIDATE_SUCCESS,
            status=200,
        )

        content = "pipeline { agent any; stages { stage('Build') { steps { echo 'hi' } } } }"
        result = validate_jenkinsfile(jenkins_client, content)

        assert result["result"] == "success"

    @responses.activate
    def test_invalid_jenkinsfile(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        responses.add(
            responses.POST,
            _VALIDATE_URL,
            json=SAMPLE_VALIDATE_WITH_ERRORS,
            status=200,
        )

        content = "invalid pipeline content"
        result = validate_jenkinsfile(jenkins_client, content)

        assert result["result"] == "failure"
        assert len(result["data"]["errors"]) == 1

    @responses.activate
    def test_auth_error(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        responses.add(
            responses.POST,
            _VALIDATE_URL,
            status=401,
        )

        with pytest.raises(JenkinsAuthError):
            validate_jenkinsfile(jenkins_client, "pipeline { }")

    @responses.activate
    def test_sends_content_as_form_data(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/crumbIssuer/api/json",
            json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"},
            status=200,
        )
        responses.add(
            responses.POST,
            _VALIDATE_URL,
            json={"result": "success"},
            status=200,
        )

        pipeline_content = "pipeline { agent any; stages { stage('CI') { steps { sh 'make' } } } }"
        validate_jenkinsfile(jenkins_client, pipeline_content)

        # Verify the pipeline content was sent
        post_call = [
            c for c in responses.calls
            if c.request.url == _VALIDATE_URL
        ][0]
        body = post_call.request.body
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        assert "jenkinsfile" in body
        assert "CI" in body


# ==================================================================
# get_pending_input
# ==================================================================


class TestGetPendingInput:
    @responses.activate
    def test_returns_pending_actions(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _pending_url(JOB_NAME, BUILD_NUMBER),
            json=SAMPLE_PENDING_INPUT_ACTIONS,
            status=200,
        )

        result = get_pending_input(jenkins_client, JOB_NAME, BUILD_NUMBER)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == "a1b2c3d4"
        assert result[0]["message"] == "Approve deployment?"
        assert len(result[0]["inputs"]) == 1

    @responses.activate
    def test_no_pending_actions(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _pending_url(JOB_NAME, BUILD_NUMBER),
            json=SAMPLE_PENDING_EMPTY,
            status=200,
        )

        result = get_pending_input(jenkins_client, JOB_NAME, BUILD_NUMBER)

        assert isinstance(result, list)
        assert len(result) == 0

    @responses.activate
    def test_job_not_found(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _pending_url("no-such-job", 1),
            status=404,
        )

        with pytest.raises(JenkinsNotFoundError):
            get_pending_input(jenkins_client, "no-such-job", 1)

    @responses.activate
    def test_api_error(self, jenkins_client: JenkinsClient) -> None:
        responses.add(
            responses.GET,
            _pending_url(JOB_NAME, BUILD_NUMBER),
            status=500,
        )

        with pytest.raises(JenkinsAPIError):
            get_pending_input(jenkins_client, JOB_NAME, BUILD_NUMBER)


# ==================================================================
# CLI tests — pipeline
# ==================================================================


def _pipe_client() -> JenkinsClient:
    return JenkinsClient(BASE_URL, username="admin", token="fake-token")


def _register_crumb_pipeline() -> None:
    responses.add(responses.GET, f"{BASE_URL}/crumbIssuer/api/json",
                  json={"crumb": "abc", "crumbRequestField": "Jenkins-Crumb"}, status=200)


class TestCLIPipelineStages:
    @responses.activate
    def test_stages_output(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/job/{JOB_NAME}/{BUILD_NUMBER}/wfapi/describe",
                       json={"id": "42", "status": "SUCCESS", "stages": [
                           {"id": "1", "name": "Build", "status": "SUCCESS"},
                           {"id": "2", "name": "Test", "status": "SUCCESS"}]}, status=200)

        from jcli.plugins.pipeline import pipeline_group
        runner = CliRunner()
        result = runner.invoke(pipeline_group, ["stages", JOB_NAME, str(BUILD_NUMBER)],
                                obj={"client": _pipe_client(), "format": "json"})
        assert result.exit_code == 0
        assert "SUCCESS" in result.output

    @responses.activate
    def test_stages_not_found(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/job/nonexistent/1/wfapi/describe", status=404)
        from jcli.plugins.pipeline import pipeline_group
        runner = CliRunner()
        result = runner.invoke(pipeline_group, ["stages", "nonexistent", "1"],
                                obj={"client": _pipe_client(), "format": "table"})
        assert result.exit_code == 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()


class TestCLIPipelineLog:
    @responses.activate
    def test_log_output(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/job/{JOB_NAME}/{BUILD_NUMBER}/execution/node/7/wfapi/log",
                       json={"nodeId": "7", "nodeStatus": "SUCCESS", "text": "hello world\n"}, status=200)

        from jcli.plugins.pipeline import pipeline_group
        runner = CliRunner()
        result = runner.invoke(pipeline_group, ["log", JOB_NAME, str(BUILD_NUMBER), "7"],
                                obj={"client": _pipe_client(), "format": "json"})
        assert result.exit_code == 0


class TestCLIPipelineValidate:
    @responses.activate
    def test_validate_success(self) -> None:
        _register_crumb_pipeline()
        responses.add(responses.POST, f"{BASE_URL}/pipeline-model-converter/validate",
                       json={"result": "success", "data": {"result": "success", "errors": []}}, status=200)

        content = 'pipeline { agent any; stages { stage("Build") { steps { echo "hi" } } } }'
        with NamedTemporaryFile(mode="w", suffix=".jenkinsfile", delete=False) as f:
            f.write(content)
            f.flush()
            tmp_path = f.name

        try:
            from jcli.plugins.pipeline import pipeline_group
            runner = CliRunner()
            result = runner.invoke(pipeline_group, ["validate", tmp_path],
                                    obj={"client": _pipe_client(), "format": "json"})
            assert result.exit_code == 0
            assert "success" in result.output
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestCLIPipelinePending:
    @responses.activate
    def test_pending_actions(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/job/{JOB_NAME}/{BUILD_NUMBER}/wfapi/pendingInputActions",
                       json=[{"id": "abc", "message": "Approve?", "inputs": []}], status=200)

        from jcli.plugins.pipeline import pipeline_group
        runner = CliRunner()
        result = runner.invoke(pipeline_group, ["pending", JOB_NAME, str(BUILD_NUMBER)],
                                obj={"client": _pipe_client(), "format": "json"})
        assert result.exit_code == 0
        assert "abc" in result.output

    @responses.activate
    def test_pending_empty(self) -> None:
        responses.add(responses.GET, f"{BASE_URL}/job/{JOB_NAME}/{BUILD_NUMBER}/wfapi/pendingInputActions",
                       json=[], status=200)

        from jcli.plugins.pipeline import pipeline_group
        runner = CliRunner()
        result = runner.invoke(pipeline_group, ["pending", JOB_NAME, str(BUILD_NUMBER)],
                                obj={"client": _pipe_client(), "format": "json"})
        assert result.exit_code == 0
