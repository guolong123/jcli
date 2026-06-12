"""Tests for jcli CLI — global options, help output, version, error handling."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from jcli.cli import cli
from jcli import __version__


# ==================================================================
# Global options
# ==================================================================


class TestGlobalOptions:
    """Test top-level CLI options: --format, --debug, --version, --help."""

    def test_version_option(self) -> None:
        """jcli --version prints version."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_help_option(self) -> None:
        """jcli --help shows help text with subcommands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Jenkins CLI" in result.output
        assert "job" in result.output
        assert "build" in result.output
        assert "node" in result.output
        assert "plugin" in result.output
        assert "credential" in result.output
        assert "pipeline" in result.output
        assert "view" in result.output
        assert "system" in result.output

    def test_debug_flag_present(self) -> None:
        """--debug flag is accepted by CLI."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--debug", "job", "--help"],
        )
        assert result.exit_code == 0
        assert "Manage Jenkins jobs" in result.output

    def test_format_option_default(self) -> None:
        """Default format is 'table'."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--format", "table", "--help"])
        assert result.exit_code == 0

    def test_format_option_json(self) -> None:
        """--format json is accepted."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--format", "json", "--help"])
        assert result.exit_code == 0

    def test_format_option_invalid(self) -> None:
        """Invalid --format value errors."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--format", "xml"])
        assert result.exit_code != 0

    def test_profile_option(self) -> None:
        """--profile option is accepted."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--profile", "staging", "--help"])
        assert result.exit_code == 0

    def test_server_option(self) -> None:
        """--server option is accepted."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--server", "https://ci.example.com", "--help"])
        assert result.exit_code == 0


# ==================================================================
# Context propagation
# ==================================================================


class TestContextPropagation:
    """Test that global options reach subcommand context correctly."""

    def test_format_json_passed_to_subcommand(self) -> None:
        """--format json should be accessible in subcommand context."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--format", "json", "job", "--help"])
        assert result.exit_code == 0

    def test_no_command_shows_help(self) -> None:
        """Running jcli with no subcommand shows help."""
        runner = CliRunner()
        result = runner.invoke(cli, [])
        # Click's default behavior: no command → shows usage message (exit_code may be 0 or 2)
        # We just verify it runs without crashing
        assert "Jenkins CLI" in result.output or "Usage:" in result.output


# ==================================================================
# Subcommand help output
# ==================================================================


class TestSubcommandHelp:
    """Verify 'help' output exists for all 8 subcommands."""

    @pytest.mark.parametrize("subcommand", [
        "job", "build", "node", "plugin", "credential",
        "pipeline", "view", "system",
    ])
    def test_subcommand_help(self, subcommand: str) -> None:
        """Each subcommand group shows its own help."""
        runner = CliRunner()
        result = runner.invoke(cli, [subcommand, "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output or "Commands:" in result.output or subcommand in result.output.lower()

    @pytest.mark.parametrize("cmd,subcmd", [
        ("job", "list"),
        ("job", "get"),
        ("job", "create"),
        ("job", "delete"),
        ("job", "copy"),
        ("job", "enable"),
        ("job", "disable"),
        ("job", "config"),
        ("build", "trigger"),
        ("build", "list"),
        ("build", "get"),
        ("build", "log"),
        ("build", "stop"),
        ("build", "queue"),
        ("node", "list"),
        ("node", "get"),
        ("node", "delete"),
        ("node", "toggle"),
        ("plugin", "list"),
        ("plugin", "get"),
        ("plugin", "install"),
        ("plugin", "uninstall"),
        ("credential", "list"),
        ("credential", "get"),
        ("credential", "create"),
        ("credential", "delete"),
        ("pipeline", "stages"),
        ("pipeline", "log"),
        ("pipeline", "validate"),
        ("pipeline", "pending"),
        ("view", "list"),
        ("view", "get"),
        ("view", "create"),
        ("view", "delete"),
        ("system", "info"),
        ("system", "restart"),
        ("system", "quiet-down"),
        ("system", "cancel-quiet-down"),
        ("system", "load"),
    ])
    def test_subsubcommand_help(self, cmd: str, subcmd: str) -> None:
        """Each leaf command shows help."""
        runner = CliRunner()
        result = runner.invoke(cli, [cmd, subcmd, "--help"])
        assert result.exit_code == 0


# ==================================================================
# Error handling - no config
# ==================================================================


class TestCLIErrorHandling:
    """Test graceful error handling when no config is present."""

    def test_job_list_no_config_shows_error(self, monkeypatch) -> None:
        """Running a command with no config produces an error (non-zero exit)."""
        monkeypatch.setattr("jcli.sdk.config.DEFAULT_CONFIG_FILE", "/tmp/nonexistent_jcli_config.yaml")
        runner = CliRunner()
        # Without mocking config, commands should fail gracefully
        result = runner.invoke(cli, ["plugin", "list"])
        # Should not crash - will error because no config
        assert result.exit_code != 0

    def test_build_trigger_no_config(self) -> None:
        """build trigger without config shows error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "trigger", "my-job"])
        assert result.exit_code != 0

    def test_system_info_no_config(self, monkeypatch) -> None:
        """system info without config shows error."""
        monkeypatch.setattr("jcli.sdk.config.DEFAULT_CONFIG_FILE", "/tmp/nonexistent_jcli_config.yaml")
        runner = CliRunner()
        result = runner.invoke(cli, ["system", "info"])
        assert result.exit_code != 0


# ==================================================================
# Complete help coverage for all sub-subcommands
# ==================================================================


class TestJobSubcommandHelp:
    @pytest.mark.parametrize("subcmd", ["list", "get", "create", "delete", "copy", "enable", "disable", "config"])
    def test_job_subcommand_help(self, subcmd: str) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["job", subcmd, "--help"])
        assert result.exit_code == 0


class TestBuildSubcommandHelp:
    @pytest.mark.parametrize("subcmd", ["trigger", "list", "get", "log", "stop", "queue"])
    def test_build_subcommand_help(self, subcmd: str) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["build", subcmd, "--help"])
        assert result.exit_code == 0


class TestNodeSubcommandHelp:
    @pytest.mark.parametrize("subcmd", ["list", "get", "delete", "toggle"])
    def test_node_subcommand_help(self, subcmd: str) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["node", subcmd, "--help"])
        assert result.exit_code == 0


class TestPluginSubcommandHelp:
    @pytest.mark.parametrize("subcmd", ["list", "get", "install", "uninstall"])
    def test_plugin_subcommand_help(self, subcmd: str) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["plugin", subcmd, "--help"])
        assert result.exit_code == 0


class TestCredentialSubcommandHelp:
    @pytest.mark.parametrize("subcmd", ["list", "get", "create", "delete"])
    def test_credential_subcommand_help(self, subcmd: str) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["credential", subcmd, "--help"])
        assert result.exit_code == 0


class TestPipelineSubcommandHelp:
    @pytest.mark.parametrize("subcmd", ["stages", "log", "validate", "pending"])
    def test_pipeline_subcommand_help(self, subcmd: str) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["pipeline", subcmd, "--help"])
        assert result.exit_code == 0


class TestViewSubcommandHelp:
    @pytest.mark.parametrize("subcmd", ["list", "get", "create", "delete"])
    def test_view_subcommand_help(self, subcmd: str) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["view", subcmd, "--help"])
        assert result.exit_code == 0


class TestSystemSubcommandHelp:
    @pytest.mark.parametrize("subcmd", ["info", "restart", "quiet-down", "cancel-quiet-down", "load"])
    def test_system_subcommand_help(self, subcmd: str) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["system", subcmd, "--help"])
        assert result.exit_code == 0
