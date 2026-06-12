"""Tests for jcli.sdk.job — Job SDK functions and CLI commands."""

from __future__ import annotations

import pytest
import responses
from click.testing import CliRunner

from jcli.plugins.job import job_group
from jcli.sdk.client import JenkinsClient
from jcli.sdk.exceptions import JenkinsNotFoundError
from jcli.sdk.job import (
    copy_job,
    create_folder,
    create_job,
    delete_folder,
    delete_job,
    disable_job,
    enable_job,
    get_job,
    get_job_config,
    list_jobs,
    rename_job,
    update_job_config,
)

BASE_URL = "http://jenkins.example.com"
JOB_NAME = "test-job"
CRUMB_URL = f"{BASE_URL}/crumbIssuer/api/json"
CRUMB_RESPONSE = {"crumb": "abc123", "crumbRequestField": "Jenkins-Crumb"}


# ==================================================================
# Helpers
# ==================================================================


def make_client() -> JenkinsClient:
    """Create a JenkinsClient with dummy credentials."""
    return JenkinsClient(BASE_URL, username="admin", token="fake-token")


def _register_crumb() -> None:
    """Register a successful crumb endpoint for POST tests."""
    responses.add(responses.GET, CRUMB_URL, json=CRUMB_RESPONSE, status=200)


# ==================================================================
# SDK: list_jobs
# ==================================================================


class TestListJobs:
    @responses.activate
    def test_returns_empty_list_when_no_jobs(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json?tree=jobs%5Bname%2Curl%2Ccolor%5D",
            json={"jobs": []},
            status=200,
        )
        client = make_client()
        result = list_jobs(client)
        assert result == []

    @responses.activate
    def test_returns_jobs_list(self) -> None:
        data = {
            "jobs": [
                {"name": "job1", "url": f"{BASE_URL}/job/job1/", "color": "blue"},
                {"name": "job2", "url": f"{BASE_URL}/job/job2/", "color": "red"},
            ]
        }
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json?tree=jobs%5Bname%2Curl%2Ccolor%5D",
            json=data,
            status=200,
        )
        client = make_client()
        result = list_jobs(client)
        assert len(result) == 2
        assert result[0]["name"] == "job1"
        assert result[0]["color"] == "blue"
        assert result[1]["name"] == "job2"


# ==================================================================
# SDK: get_job
# ==================================================================


class TestGetJob:
    @responses.activate
    def test_returns_job_details(self) -> None:
        job_data = {"name": JOB_NAME, "url": f"{BASE_URL}/job/{JOB_NAME}/", "buildable": True}
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/{JOB_NAME}/api/json",
            json=job_data,
            status=200,
        )
        client = make_client()
        result = get_job(client, JOB_NAME)
        assert result["name"] == JOB_NAME
        assert result["buildable"] is True

    @responses.activate
    def test_raises_not_found_for_missing_job(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/nonexistent/api/json",
            status=404,
        )
        client = make_client()
        with pytest.raises(JenkinsNotFoundError):
            get_job(client, "nonexistent")


# ==================================================================
# SDK: create_job
# ==================================================================


class TestCreateJob:
    @responses.activate
    def test_creates_job_from_xml(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem?name={JOB_NAME}",
            status=200,
        )
        client = make_client()
        config_xml = "<project><description>Test</description></project>"
        create_job(client, JOB_NAME, config_xml)

        # [0] is crumb GET, [1] is the POST
        req = responses.calls[1].request
        assert req.method == "POST"
        assert config_xml.encode("utf-8") in req.body


# ==================================================================
# SDK: delete_job
# ==================================================================


class TestDeleteJob:
    @responses.activate
    def test_deletes_job(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/{JOB_NAME}/doDelete",
            status=200,
        )
        client = make_client()
        delete_job(client, JOB_NAME)
        assert responses.calls[1].request.url.endswith("/doDelete")

    @responses.activate
    def test_raises_not_found_when_job_missing(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/nonexistent/doDelete",
            status=404,
        )
        client = make_client()
        with pytest.raises(JenkinsNotFoundError):
            delete_job(client, "nonexistent")


# ==================================================================
# SDK: copy_job
# ==================================================================


class TestCopyJob:
    @responses.activate
    def test_copies_job(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem",
            status=200,
        )
        client = make_client()
        copy_job(client, "source-job", "copied-job")

        req = responses.calls[1].request  # [0] is crumb
        body = req.body or b""
        assert b"copied-job" in body if isinstance(body, bytes) else "copied-job" in str(body)

    @responses.activate
    def test_raises_not_found_when_source_missing(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem",
            status=404,
        )
        client = make_client()
        with pytest.raises(JenkinsNotFoundError):
            copy_job(client, "nonexistent", "new-job")


# ==================================================================
# SDK: rename_job
# ==================================================================


class TestRenameJob:
    @responses.activate
    def test_renames_job(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/{JOB_NAME}/doRename?newName=renamed-job",
            status=200,
        )
        client = make_client()
        rename_job(client, JOB_NAME, "renamed-job")
        assert responses.calls[1].request.url.endswith(
            f"/doRename?newName=renamed-job"
        )

    @responses.activate
    def test_raises_not_found_when_job_missing(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/nonexistent/doRename?newName=new-name",
            status=404,
        )
        client = make_client()
        with pytest.raises(JenkinsNotFoundError):
            rename_job(client, "nonexistent", "new-name")


# ==================================================================
# SDK: enable_job
# ==================================================================


class TestEnableJob:
    @responses.activate
    def test_enables_job(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/{JOB_NAME}/enable",
            status=200,
        )
        client = make_client()
        enable_job(client, JOB_NAME)
        assert responses.calls[1].request.url.endswith("/enable")

    @responses.activate
    def test_raises_not_found_when_job_missing(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/nonexistent/enable",
            status=404,
        )
        client = make_client()
        with pytest.raises(JenkinsNotFoundError):
            enable_job(client, "nonexistent")


# ==================================================================
# SDK: disable_job
# ==================================================================


class TestDisableJob:
    @responses.activate
    def test_disables_job(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/{JOB_NAME}/disable",
            status=200,
        )
        client = make_client()
        disable_job(client, JOB_NAME)
        assert responses.calls[1].request.url.endswith("/disable")

    @responses.activate
    def test_raises_not_found_when_job_missing(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/nonexistent/disable",
            status=404,
        )
        client = make_client()
        with pytest.raises(JenkinsNotFoundError):
            disable_job(client, "nonexistent")


# ==================================================================
# SDK: get_job_config
# ==================================================================


class TestGetJobConfig:
    @responses.activate
    def test_returns_xml_config(self) -> None:
        xml = '<project><description>Hello</description></project>'
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/{JOB_NAME}/config.xml",
            body=xml,
            status=200,
            content_type="application/xml",
        )
        client = make_client()
        result = get_job_config(client, JOB_NAME)
        assert result == xml
        assert "Hello" in result

    @responses.activate
    def test_raises_not_found_when_job_missing(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/nonexistent/config.xml",
            status=404,
        )
        client = make_client()
        with pytest.raises(JenkinsNotFoundError):
            get_job_config(client, "nonexistent")


# ==================================================================
# SDK: update_job_config
# ==================================================================


class TestUpdateJobConfig:
    @responses.activate
    def test_updates_job_config(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/{JOB_NAME}/config.xml",
            status=200,
        )
        client = make_client()
        config_xml = "<project><description>Updated</description></project>"
        update_job_config(client, JOB_NAME, config_xml)

        # [0] is crumb GET, [1] is the POST
        req = responses.calls[1].request
        assert req.method == "POST"
        assert config_xml.encode("utf-8") in req.body
        assert "/job/test-job/config.xml" in req.url

    @responses.activate
    def test_raises_not_found_when_job_missing(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/nonexistent/config.xml",
            status=404,
        )
        client = make_client()
        with pytest.raises(JenkinsNotFoundError):
            update_job_config(client, "nonexistent", "<project/>")


# ==================================================================
# SDK: create_folder
# ==================================================================


class TestCreateFolder:
    @responses.activate
    def test_creates_folder(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem?name=my-folder&mode=com.cloudbees.hudson.plugins.folder.Folder",
            status=200,
        )
        client = make_client()
        create_folder(client, "my-folder")
        assert responses.calls[1].request.url.endswith(
            "mode=com.cloudbees.hudson.plugins.folder.Folder"
        )

    @responses.activate
    def test_creates_folder_with_special_chars(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem?name=my%20folder&mode=com.cloudbees.hudson.plugins.folder.Folder",
            status=200,
        )
        client = make_client()
        create_folder(client, "my folder")
        # URL encoding should encode the space
        assert "my%20folder" in responses.calls[1].request.url

    @responses.activate
    def test_raises_error_on_duplicate_folder(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem?name=existing&mode=com.cloudbees.hudson.plugins.folder.Folder",
            status=400,
        )
        client = make_client()
        from jcli.sdk.exceptions import JenkinsAPIError
        with pytest.raises(JenkinsAPIError):
            create_folder(client, "existing")


# ==================================================================
# SDK: delete_folder
# ==================================================================


class TestDeleteFolder:
    @responses.activate
    def test_deletes_folder(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/my-folder/doDelete",
            status=200,
        )
        client = make_client()
        delete_folder(client, "my-folder")
        assert responses.calls[1].request.url.endswith("/doDelete")

    @responses.activate
    def test_raises_not_found_when_folder_missing(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/nonexistent/doDelete",
            status=404,
        )
        client = make_client()
        with pytest.raises(JenkinsNotFoundError):
            delete_folder(client, "nonexistent")


# ==================================================================
# CLI: job list
# ==================================================================


class TestCLIList:
    @responses.activate
    def test_list_jobs_json_output(self) -> None:
        """List jobs with JSON format."""
        data = {
            "jobs": [
                {"name": "job1", "url": f"{BASE_URL}/job/job1/", "color": "blue"},
            ]
        }
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json?tree=jobs%5Bname%2Curl%2Ccolor%5D",
            json=data,
            status=200,
        )
        client = make_client()
        runner = CliRunner()
        result = runner.invoke(
            job_group,
            ["list"],
            obj={"client": client, "format": "json"},
        )
        assert result.exit_code == 0
        assert "job1" in result.output

    @responses.activate
    def test_list_jobs_table_output(self) -> None:
        """List jobs with table format."""
        data = {
            "jobs": [
                {"name": "job1", "url": f"{BASE_URL}/job/job1/", "color": "blue"},
            ]
        }
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json?tree=jobs%5Bname%2Curl%2Ccolor%5D",
            json=data,
            status=200,
        )
        client = make_client()
        runner = CliRunner()
        result = runner.invoke(
            job_group,
            ["list"],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code == 0
        assert "job1" in result.output

    @responses.activate
    def test_list_jobs_empty(self) -> None:
        """List returns info message when no jobs."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json?tree=jobs%5Bname%2Curl%2Ccolor%5D",
            json={"jobs": []},
            status=200,
        )
        client = make_client()
        runner = CliRunner()
        result = runner.invoke(
            job_group,
            ["list"],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code == 0
        assert "No jobs found" in result.output


# ==================================================================
# CLI: job get
# ==================================================================


class TestCLIGet:
    @responses.activate
    def test_get_job_details(self) -> None:
        job_data = {"name": JOB_NAME, "url": f"{BASE_URL}/job/{JOB_NAME}/", "buildable": True}
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/{JOB_NAME}/api/json",
            json=job_data,
            status=200,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["get", JOB_NAME],
            obj={"client": client, "format": "json"},
        )
        assert result.exit_code == 0
        assert JOB_NAME in result.output

    @responses.activate
    def test_get_job_not_found(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/nonexistent/api/json",
            status=404,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["get", "nonexistent"],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code == 1
        assert "not found" in result.output


# ==================================================================
# CLI: job create
# ==================================================================


class TestCLICreate:
    @responses.activate
    def test_create_job_from_file(self, tmp_path) -> None:
        # Register crumb and createItem response
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem?name={JOB_NAME}",
            status=200,
        )
        # Write a temporary config XML file
        xml_content = "<project><description>TestJob</description></project>"
        config_file = tmp_path / "config.xml"
        config_file.write_text(xml_content)

        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["create", JOB_NAME, str(config_file)],
            obj={"client": client, "format": "json"},
        )
        assert result.exit_code == 0
        assert "created" in result.output

    @responses.activate
    def test_create_job_file_not_found(self) -> None:
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["create", JOB_NAME, "/nonexistent/path/config.xml"],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code != 0


# ==================================================================
# CLI: job create (parameterized)
# ==================================================================


class TestCLICreateParameterized:
    @responses.activate
    def test_parameterized_create_freestyle(self) -> None:
        """Freestyle job created via --type with Git + shell."""
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem?name=my-freestyle",
            status=200,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            [
                "create", "my-freestyle",
                "--type", "freestyle",
                "--git-url", "https://github.com/foo/bar.git",
                "--shell", "make build",
            ],
            obj={"client": client, "format": "json"},
        )
        assert result.exit_code == 0
        assert "created" in result.output

        # Verify XML content was sent in the POST body
        req = responses.calls[1].request
        body = req.body.decode("utf-8") if isinstance(req.body, bytes) else (req.body or "")
        assert "<project>" in body
        assert "https://github.com/foo/bar.git" in body
        assert "make build" in body

    @responses.activate
    def test_parameterized_create_pipeline(self) -> None:
        """Pipeline job created via --type with Git + Jenkinsfile."""
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem?name=my-pipeline",
            status=200,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            [
                "create", "my-pipeline",
                "--type", "pipeline",
                "--git-url", "https://github.com/foo/bar.git",
                "--jenkinsfile", "ci/Jenkinsfile",
            ],
            obj={"client": client, "format": "json"},
        )
        assert result.exit_code == 0
        assert "created" in result.output

        req = responses.calls[1].request
        body = req.body.decode("utf-8") if isinstance(req.body, bytes) else (req.body or "")
        assert "<flow-definition" in body
        assert "https://github.com/foo/bar.git" in body
        assert "ci/Jenkinsfile" in body

    @responses.activate
    def test_parameterized_create_missing_type(self) -> None:
        """Error when neither config_file nor --type is provided."""
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["create", "myjob"],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code != 0
        assert "Error" in result.output or "Usage" in result.output

    @responses.activate
    def test_parameterized_create_with_cron(self) -> None:
        """Freestyle job with cron trigger includes timer XML."""
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem?name=cron-job",
            status=200,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            [
                "create", "cron-job",
                "--type", "freestyle",
                "--git-url", "https://github.com/foo/bar.git",
                "--cron", "H/5 * * * *",
                "--shell", "echo hi",
            ],
            obj={"client": client, "format": "json"},
        )
        assert result.exit_code == 0
        assert "created" in result.output

        req = responses.calls[1].request
        body = req.body.decode("utf-8") if isinstance(req.body, bytes) else (req.body or "")
        assert "hudson.triggers.TimerTrigger" in body
        assert "H/5 * * * *" in body

    @responses.activate
    def test_parameterized_create_backward_compat(self, tmp_path) -> None:
        """Old file-based creation still works alongside new --type mode."""
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem?name=old-style",
            status=200,
        )
        xml_content = "<project><description>Legacy</description></project>"
        config_file = tmp_path / "config.xml"
        config_file.write_text(xml_content)

        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["create", "old-style", str(config_file)],
            obj={"client": client, "format": "json"},
        )
        assert result.exit_code == 0
        assert "created" in result.output

        req = responses.calls[1].request
        body = req.body.decode("utf-8") if isinstance(req.body, bytes) else (req.body or "")
        assert "Legacy" in body

    @responses.activate
    def test_parameterized_create_pipeline_inline_script(self) -> None:
        """Pipeline job with --script uses CpsFlowDefinition in generated XML."""
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem?name=inline-pipe",
            status=200,
        )
        runner = CliRunner()
        client = make_client()
        script_content = "pipeline { agent any; stages { stage('build') { steps { echo 'hi' } } } }"
        result = runner.invoke(
            job_group,
            [
                "create", "inline-pipe",
                "--type", "pipeline",
                "--script", script_content,
            ],
            obj={"client": client, "format": "json"},
        )
        assert result.exit_code == 0
        assert "created" in result.output

        req = responses.calls[1].request
        body = req.body.decode("utf-8") if isinstance(req.body, bytes) else (req.body or "")
        assert "<flow-definition" in body
        assert "CpsFlowDefinition" in body
        assert "echo 'hi'" in body
        assert "<sandbox>true</sandbox>" in body
        # Must NOT contain SCM-based definition
        assert "CpsScmFlowDefinition" not in body

    @responses.activate
    def test_parameterized_create_pipeline_script_with_git(self) -> None:
        """Script mode takes precedence even when git-url is also provided."""
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem?name=script-git",
            status=200,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            [
                "create", "script-git",
                "--type", "pipeline",
                "--git-url", "https://github.com/foo/bar.git",
                "--script", "pipeline { agent any; stages { stage('deploy') { steps { sh 'deploy.sh' } } } }",
            ],
            obj={"client": client, "format": "json"},
        )
        assert result.exit_code == 0
        assert "created" in result.output

        req = responses.calls[1].request
        body = req.body.decode("utf-8") if isinstance(req.body, bytes) else (req.body or "")
        assert "<flow-definition" in body
        assert "CpsFlowDefinition" in body
        assert "deploy.sh" in body
        # Script mode takes priority — no CpsScmFlowDefinition
        assert "CpsScmFlowDefinition" not in body

    @responses.activate
    def test_parameterized_create_pipeline_scm_default(self) -> None:
        """SCM-based pipeline still works without --script (existing behaviour)."""
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem?name=scm-pipe",
            status=200,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            [
                "create", "scm-pipe",
                "--type", "pipeline",
                "--git-url", "https://github.com/acme/repo.git",
                "--git-branch", "develop",
                "--jenkinsfile", "ci/Jenkinsfile",
            ],
            obj={"client": client, "format": "json"},
        )
        assert result.exit_code == 0
        assert "created" in result.output

        req = responses.calls[1].request
        body = req.body.decode("utf-8") if isinstance(req.body, bytes) else (req.body or "")
        assert "<flow-definition" in body
        assert "CpsScmFlowDefinition" in body
        assert "https://github.com/acme/repo.git" in body
        assert "*/develop" in body
        assert "ci/Jenkinsfile" in body
        # Must NOT contain inline script definition
        assert "CpsFlowDefinition" not in body


# ==================================================================
# CLI: job update
# ==================================================================


class TestCLIUpdate:
    @responses.activate
    def test_update_job_from_file(self, tmp_path) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/{JOB_NAME}/config.xml",
            status=200,
        )
        xml_content = "<project><description>UpdatedJob</description></project>"
        config_file = tmp_path / "config.xml"
        config_file.write_text(xml_content)

        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["update", JOB_NAME, str(config_file)],
            obj={"client": client, "format": "json"},
        )
        assert result.exit_code == 0
        assert "updated" in result.output

    @responses.activate
    def test_update_job_table_output(self, tmp_path) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/{JOB_NAME}/config.xml",
            status=200,
        )
        xml_content = "<project><description>UpdatedJob</description></project>"
        config_file = tmp_path / "config.xml"
        config_file.write_text(xml_content)

        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["update", JOB_NAME, str(config_file)],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code == 0
        assert "updated" in result.output

    @responses.activate
    def test_update_job_not_found(self, tmp_path) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/nonexistent/config.xml",
            status=404,
        )
        xml_content = "<project/>"
        config_file = tmp_path / "config.xml"
        config_file.write_text(xml_content)

        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["update", "nonexistent", str(config_file)],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_update_job_file_not_found(self) -> None:
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["update", JOB_NAME, "/nonexistent/path/config.xml"],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code != 0


# ==================================================================
# CLI: job delete
# ==================================================================


class TestCLIDelete:
    @responses.activate
    def test_delete_without_yes_prompts_and_cancels(self) -> None:
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["delete", JOB_NAME],
            obj={"client": client, "format": "table"},
            input="n\n",
        )
        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()

    @responses.activate
    def test_delete_with_yes_flag_skips_prompt(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/{JOB_NAME}/doDelete",
            status=200,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["delete", JOB_NAME, "--yes"],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code == 0
        assert "deleted" in result.output.lower()

    @responses.activate
    def test_delete_job_not_found(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/nonexistent/doDelete",
            status=404,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["delete", "nonexistent", "--yes"],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code == 1
        assert "not found" in result.output


# ==================================================================
# CLI: job copy
# ==================================================================


class TestCLICopy:
    @responses.activate
    def test_copy_job(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem",
            status=200,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["copy", "source-job", "copied-job"],
            obj={"client": client, "format": "json"},
        )
        assert result.exit_code == 0
        assert "copied" in result.output.lower()

    @responses.activate
    def test_copy_job_source_not_found(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem",
            status=404,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["copy", "nonexistent", "new-job"],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code == 1
        assert "not found" in result.output


# ==================================================================
# CLI: job rename
# ==================================================================


class TestCLIRename:
    @responses.activate
    def test_rename_job(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/{JOB_NAME}/doRename?newName=renamed-job",
            status=200,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["rename", JOB_NAME, "renamed-job"],
            obj={"client": client, "format": "json"},
        )
        assert result.exit_code == 0
        assert "renamed" in result.output.lower()

    @responses.activate
    def test_rename_job_not_found(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/nonexistent/doRename?newName=new-name",
            status=404,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["rename", "nonexistent", "new-name"],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code == 1
        assert "not found" in result.output


# ==================================================================
# CLI: job enable / disable
# ==================================================================


class TestCLIEnableDisable:
    @responses.activate
    def test_enable_job(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/{JOB_NAME}/enable",
            status=200,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["enable", JOB_NAME],
            obj={"client": client, "format": "json"},
        )
        assert result.exit_code == 0
        assert "enabled" in result.output.lower()

    @responses.activate
    def test_enable_job_not_found(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/nonexistent/enable",
            status=404,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["enable", "nonexistent"],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    @responses.activate
    def test_disable_job(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/{JOB_NAME}/disable",
            status=200,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["disable", JOB_NAME],
            obj={"client": client, "format": "json"},
        )
        assert result.exit_code == 0
        assert "disabled" in result.output.lower()

    @responses.activate
    def test_disable_job_not_found(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/nonexistent/disable",
            status=404,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["disable", "nonexistent"],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code == 1
        assert "not found" in result.output


# ==================================================================
# CLI: job config
# ==================================================================


class TestCLIConfig:
    @responses.activate
    def test_config_prints_xml(self) -> None:
        xml = '<project><description>Hello</description></project>'
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/{JOB_NAME}/config.xml",
            body=xml,
            status=200,
            content_type="application/xml",
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["config", JOB_NAME],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code == 0
        assert "Hello" in result.output

    @responses.activate
    def test_config_job_not_found(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/nonexistent/config.xml",
            status=404,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["config", "nonexistent"],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code == 1
        assert "not found" in result.output


# ==================================================================
# CLI: job create-folder
# ==================================================================


class TestCLICreateFolder:
    @responses.activate
    def test_create_folder_success(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem?name=my-folder&mode=com.cloudbees.hudson.plugins.folder.Folder",
            status=200,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["create-folder", "my-folder"],
            obj={"client": client, "format": "json"},
        )
        assert result.exit_code == 0
        assert "created" in result.output.lower()

    @responses.activate
    def test_create_folder_table_output(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem?name=my-folder&mode=com.cloudbees.hudson.plugins.folder.Folder",
            status=200,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["create-folder", "my-folder"],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code == 0
        assert "created" in result.output.lower()

    @responses.activate
    def test_create_folder_api_error(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/createItem?name=bad&mode=com.cloudbees.hudson.plugins.folder.Folder",
            status=400,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["create-folder", "bad"],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code == 1


# ==================================================================
# CLI: job delete-folder
# ==================================================================


class TestCLIDeleteFolder:
    @responses.activate
    def test_delete_folder_with_yes_flag(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/my-folder/doDelete",
            status=200,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["delete-folder", "my-folder", "--yes"],
            obj={"client": client, "format": "json"},
        )
        assert result.exit_code == 0
        assert "deleted" in result.output.lower()

    @responses.activate
    def test_delete_folder_not_found(self) -> None:
        _register_crumb()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/nonexistent/doDelete",
            status=404,
        )
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["delete-folder", "nonexistent", "--yes"],
            obj={"client": client, "format": "table"},
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_delete_folder_aborts_without_yes(self) -> None:
        runner = CliRunner()
        client = make_client()
        result = runner.invoke(
            job_group,
            ["delete-folder", "my-folder"],
            obj={"client": client, "format": "table"},
            input="n\n",
        )
        assert result.exit_code == 1  # click.confirm aborts with SystemExit(1)


# ==================================================================
# CLI: additional format & edge case tests
# ==================================================================


class TestCLIJobYamlFormat:
    @responses.activate
    def test_list_yaml_output(self) -> None:
        data = {
            "jobs": [
                {"name": "job1", "url": f"{BASE_URL}/job/job1/", "color": "blue"},
            ]
        }
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/json?tree=jobs%5Bname%2Curl%2Ccolor%5D",
            json=data,
            status=200,
        )
        client = make_client()
        runner = CliRunner()
        result = runner.invoke(
            job_group,
            ["list"],
            obj={"client": client, "format": "yaml"},
        )
        assert result.exit_code == 0
        assert "job1" in result.output

    @responses.activate
    def test_get_yaml_output(self) -> None:
        job_data = {"name": JOB_NAME, "url": f"{BASE_URL}/job/{JOB_NAME}/", "buildable": True}
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/{JOB_NAME}/api/json",
            json=job_data,
            status=200,
        )
        client = make_client()
        runner = CliRunner()
        result = runner.invoke(
            job_group,
            ["get", JOB_NAME],
            obj={"client": client, "format": "yaml"},
        )
        assert result.exit_code == 0
        assert JOB_NAME in result.output


class TestCLIJobEdgeCases:
    def test_job_help_shows_all_subcommands(self) -> None:
        runner = CliRunner()
        result = runner.invoke(job_group, ["--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "create" in result.output
        assert "create-folder" in result.output
        assert "delete-folder" in result.output
        assert "update" in result.output
        assert "delete" in result.output
        assert "copy" in result.output
        assert "rename" in result.output
        assert "enable" in result.output
        assert "disable" in result.output
        assert "config" in result.output
