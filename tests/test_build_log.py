"""Tests for ``jcli build log`` (cliyard plugin ``jenkins_build_log``).

Tail semantics: no flags prints the whole log; ``-n N`` limits to the last
*N* lines; ``-f`` follows live (history first, then newly appended lines).
Follow polls the full console text and slices locally by byte offset, so it
works even when Jenkins ignores ``?start=`` (no reprints, no loops).
"""

from __future__ import annotations

import pytest
import responses
from click.testing import CliRunner

from jcli.cli import cli

BASE_URL = "http://jenkins.example.com"
LOG_URL = f"{BASE_URL}/job/my-job/42/consoleText"
BUILD_URL = f"{BASE_URL}/job/my-job/42/api/json"


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


@responses.activate
def test_log_prints_full_text(runner, isolated_config) -> None:
    responses.add(
        responses.GET,
        LOG_URL,
        body="Started by user\n[INFO] done\n",
        status=200,
    )
    result = runner.invoke(cli, ["build", "log", "my-job", "42"])
    assert result.exit_code == 0
    assert result.output == "Started by user\n[INFO] done\n"


@responses.activate
def test_log_prints_tail_lines(runner, isolated_config) -> None:
    """-n N without -f prints only the last N lines."""
    responses.add(
        responses.GET,
        LOG_URL,
        body="line1\nline2\nline3\n",
        status=200,
    )
    result = runner.invoke(cli, ["build", "log", "my-job", "42", "-n", "2"])
    assert result.exit_code == 0
    assert result.output == "line2\nline3\n"


@responses.activate
def test_log_follow_streams_increments(runner, isolated_config, monkeypatch) -> None:
    """-f prints the whole history, then only newly appended lines."""
    monkeypatch.setattr("time.sleep", lambda s: None)

    responses.add(responses.GET, LOG_URL, body="line1\n", status=200)
    responses.add(
        responses.GET,
        LOG_URL,
        body="line1\nline2\n",
        status=200,
    )
    responses.add(
        responses.GET,
        LOG_URL,
        body="line1\nline2\n",
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BUILD_URL}?tree=building",
        json={"building": True},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BUILD_URL}?tree=building",
        json={"building": False},
        status=200,
    )

    result = runner.invoke(cli, ["build", "log", "my-job", "42", "-f"])
    assert result.exit_code == 0
    assert result.output == "line1\nline2\n\n"


@responses.activate
def test_log_follow_with_tail_lines(runner, isolated_config, monkeypatch) -> None:
    """-f -n N prints the last N lines of history, then streams new lines."""
    monkeypatch.setattr("time.sleep", lambda s: None)

    responses.add(
        responses.GET,
        LOG_URL,
        body="line1\nline2\nline3\n",
        status=200,
    )
    responses.add(
        responses.GET,
        LOG_URL,
        body="line1\nline2\nline3\nline4\n",
        status=200,
    )
    responses.add(
        responses.GET,
        LOG_URL,
        body="line1\nline2\nline3\nline4\n",
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BUILD_URL}?tree=building",
        json={"building": True},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BUILD_URL}?tree=building",
        json={"building": False},
        status=200,
    )

    result = runner.invoke(cli, ["build", "log", "my-job", "42", "-f", "-n", "2"])
    assert result.exit_code == 0
    assert result.output == "line2\nline3\nline4\n\n"


@responses.activate
def test_log_follow_exits_when_build_never_running(runner, isolated_config, monkeypatch) -> None:
    """Build already finished: history printed, then follow exits."""
    monkeypatch.setattr("time.sleep", lambda s: None)

    responses.add(responses.GET, LOG_URL, body="Finished: SUCCESS\n", status=200)
    responses.add(
        responses.GET,
        LOG_URL,
        body="Finished: SUCCESS\n",
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BUILD_URL}?tree=building",
        json={"building": False},
        status=200,
    )

    result = runner.invoke(cli, ["build", "log", "my-job", "42", "-f"])
    assert result.exit_code == 0
    assert result.output == "Finished: SUCCESS\n\n"


@responses.activate
def test_log_follow_static_log_does_not_loop(runner, isolated_config, monkeypatch) -> None:
    """Log stopped growing: nothing reprinted, follow exits when build ends."""
    monkeypatch.setattr("time.sleep", lambda s: None)

    responses.add(responses.GET, LOG_URL, body="line1\nline2\n", status=200)
    responses.add(responses.GET, LOG_URL, body="line1\nline2\n", status=200)
    responses.add(responses.GET, LOG_URL, body="line1\nline2\n", status=200)
    responses.add(
        responses.GET,
        f"{BUILD_URL}?tree=building",
        json={"building": True},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BUILD_URL}?tree=building",
        json={"building": False},
        status=200,
    )

    result = runner.invoke(cli, ["build", "log", "my-job", "42", "-f"])
    assert result.exit_code == 0
    assert result.output == "line1\nline2\n\n"
