"""Tests for ``jcli build rebuild`` / ``jcli build replay`` (cliyard plugins
``jenkins_build_rebuild`` and ``jenkins_build_replay``).

Covers the rebuild flow end-to-end through the generated CLI:
auto-fetch previous build parameters, ``--set`` overrides, no-parameter
builds, and a failed parameters lookup (graceful fallback to /build).
Also covers the real Replay flow: form-posted Jenkinsfile to
``/replay/run`` with the four verified form fields.
All HTTP is mocked with ``responses`` (no real Jenkins required).
"""

from __future__ import annotations

import urllib.parse

import pytest
import responses
from click.testing import CliRunner

from jcli.cli import cli

BASE_URL = "http://jenkins.example.com"
CRUMB_URL = f"{BASE_URL}/crumbIssuer/api/json"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Point the config file at a temp profile and drop env overrides."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "active_profile: default\n"
        "profiles:\n"
        "  default:\n"
        "    url: %s\n"
        "    username: admin\n"
        "    api_token: fake-token\n" % BASE_URL,
        encoding="utf-8",
    )
    monkeypatch.setattr("jcli.sdk.config.DEFAULT_CONFIG_FILE", cfg)
    monkeypatch.delenv("JCLI_URL", raising=False)
    monkeypatch.delenv("JCLI_PROFILE", raising=False)
    return cfg


def _mock_crumb_disabled():
    responses.add(responses.GET, CRUMB_URL, status=404)


def _mock_crumb_enabled(crumb: str = "abc123"):
    responses.add(
        responses.GET,
        CRUMB_URL,
        json={"crumbRequestField": "Jenkins-Crumb", "crumb": crumb},
        status=200,
    )


def _mock_queue_item(item_id: int):
    """POST 302 Location 会被 requests 自动跟随，mock 队列项页面。"""
    responses.add(
        responses.GET,
        f"{BASE_URL}/queue/item/{item_id}/",
        json={"id": item_id},
        status=200,
    )


def _post_calls():
    return [c for c in responses.calls if c.request.method == "POST"]


def _post_query(url: str) -> str:
    return urllib.parse.urlparse(url).query


@pytest.mark.usefixtures("isolated_config")
class TestBuildRebuild:
    @responses.activate
    def test_rebuild_auto_fetches_previous_params(self, runner):
        """No --set: parameters are taken from the previous build."""
        _mock_crumb_disabled()
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/my-job/5/api/json",
            json={
                "actions": [
                    {"parameters": [{"name": "BRANCH", "value": "main"}, {"name": "TAG", "value": "v1"}]}
                ]
            },
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/my-job/buildWithParameters",
            status=302,
            headers={"Location": "/queue/item/100/"},
        )
        _mock_queue_item(100)
        _mock_queue_item(100)

        result = runner.invoke(cli, ["build", "rebuild", "my-job", "5"])

        assert result.exit_code == 0, result.output
        post = _post_calls()[0]
        assert "/job/my-job/buildWithParameters" in post.request.url
        assert _post_query(post.request.url) == "BRANCH=main&TAG=v1"
        assert "parameters" in result.output
        assert "BRANCH" in result.output

    @responses.activate
    def test_rebuild_set_overrides_previous_params(self, runner):
        """--set overrides an auto-fetched parameter, others are kept."""
        _mock_crumb_disabled()
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/my-job/5/api/json",
            json={"actions": [{"parameters": [{"name": "BRANCH", "value": "main"}, {"name": "TAG", "value": "v1"}]}]},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/my-job/buildWithParameters",
            status=302,
            headers={"Location": "/queue/item/100/"},
        )
        _mock_queue_item(100)
        _mock_queue_item(100)

        result = runner.invoke(cli, ["build", "rebuild", "my-job", "5", "--set", "BRANCH=fix"])

        assert result.exit_code == 0, result.output
        post = _post_calls()[0]
        query = dict(urllib.parse.parse_qsl(_post_query(post.request.url)))
        assert query == {"BRANCH": "fix", "TAG": "v1"}

    @responses.activate
    def test_rebuild_no_parameters_uses_plain_build(self, runner):
        """Previous build has no parameters -> POST /build without params."""
        _mock_crumb_disabled()
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/my-job/5/api/json",
            json={"actions": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/my-job/build",
            status=302,
            headers={"Location": "/queue/item/101/"},
        )
        _mock_queue_item(101)

        result = runner.invoke(cli, ["build", "rebuild", "my-job", "5"])

        assert result.exit_code == 0, result.output
        post = _post_calls()[0]
        assert post.request.url == f"{BASE_URL}/job/my-job/build"
        assert "parameters" in result.output

    @responses.activate
    def test_rebuild_params_lookup_failure_falls_back_to_build(self, runner):
        """Previous params fetch fails -> still trigger /build."""
        _mock_crumb_disabled()
        responses.add(
            responses.GET,
            f"{BASE_URL}/job/my-job/5/api/json",
            body="server error",
            status=500,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/my-job/build",
            status=302,
            headers={"Location": "/queue/item/102/"},
        )
        _mock_queue_item(102)

        result = runner.invoke(cli, ["build", "rebuild", "my-job", "5"])

        assert result.exit_code == 0, result.output
        post = _post_calls()[0]
        assert post.request.url == f"{BASE_URL}/job/my-job/build"
        assert "parameters" in result.output


@pytest.mark.usefixtures("isolated_config")
class TestBuildReplay:
    def _replay_jenkinsfile(self, tmp_path) -> str:
        """Write a throwaway Jenkinsfile and return its path."""
        jf = tmp_path / "replay.jenkinsfile"
        jf.write_text("pipeline { agent any; stages { stage('x') { steps { echo 'hi' } } } }\n", encoding="utf-8")
        return str(jf)

    def _assert_replay_form(self, post) -> None:
        """Assert the form body carries the four verified Replay fields."""
        body = post.request.body
        assert body is not None
        for key in ("_.mainScript", "Submit", "Jenkins-Crumb", "json"):
            assert f"{key}=" in body
        assert "Jenkins-Crumb=abc123" in body
        assert urllib.parse.quote("运行") in body
        assert "mainScript" in body

    @responses.activate
    def test_replay_posts_jenkinsfile_to_replay_run(self, runner, tmp_path):
        """Replay form-posts the Jenkinsfile content to /replay/run."""
        _mock_crumb_enabled("abc123")
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/my-job/5/replay/run",
            status=302,
            headers={"Location": "/queue/item/200/"},
        )

        result = runner.invoke(
            cli,
            ["build", "replay", "my-job", "5", self._replay_jenkinsfile(tmp_path)],
        )

        assert result.exit_code == 0, result.output
        post = _post_calls()[0]
        assert post.request.url == f"{BASE_URL}/job/my-job/5/replay/run"
        self._assert_replay_form(post)
        assert "replayed" in result.output

    @responses.activate
    def test_replay_failure_reports_code_and_detail(self, runner, tmp_path):
        """Non-302/200 response surfaces status + detail instead of raising."""
        _mock_crumb_disabled()
        responses.add(
            responses.POST,
            f"{BASE_URL}/job/my-job/5/replay/run",
            body="bad request",
            status=400,
        )

        result = runner.invoke(
            cli,
            ["build", "replay", "my-job", "5", self._replay_jenkinsfile(tmp_path)],
        )

        assert result.exit_code == 0, result.output
        assert "failed" in result.output
        assert "400" in result.output
