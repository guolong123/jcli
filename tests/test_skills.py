"""Tests for jcli.plugins.skills — Skills management commands."""

from __future__ import annotations

import pytest
from click.testing import CliRunner
from pathlib import Path

from jcli.plugins.skills import (
    skills_group,
    get_bundled_skills,
    get_installed_skills,
    parse_skill_metadata,
    find_skill_dir,
    BUNDLED_SKILLS_DIR,
    DEFAULT_INSTALL_DIR,
)


# ==================================================================
# Helpers
# ==================================================================


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def temp_install_dir(tmp_path: Path) -> Path:
    return tmp_path / "skills"


# ==================================================================
# parse_skill_metadata
# ==================================================================


class TestParseSkillMetadata:
    def test_parses_frontmatter(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: my-skill\n"
            "version: 1.0.0\n"
            "description: Test skill\n"
            "allowed-tools:\n"
            "  - Bash\n"
            "  - Read\n"
            "---\n"
            "# My Skill\n"
            "Content here."
        )

        metadata = parse_skill_metadata(skill_dir)
        assert metadata["name"] == "my-skill"
        assert metadata["version"] == "1.0.0"
        assert metadata["description"] == "Test skill"
        assert "Bash" in metadata["allowed_tools"]
        assert "Read" in metadata["allowed_tools"]

    def test_returns_defaults_when_no_frontmatter(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("# My Skill\nContent here.")

        metadata = parse_skill_metadata(skill_dir)
        assert metadata["name"] == "test-skill"
        assert metadata["version"] == ""
        assert metadata["description"] == ""

    def test_returns_defaults_when_no_skill_md(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()

        metadata = parse_skill_metadata(skill_dir)
        assert metadata["name"] == "test-skill"
        assert metadata["version"] == ""


# ==================================================================
# get_bundled_skills
# ==================================================================


class TestGetBundledSkills:
    def test_returns_list_of_bundled_skills(self) -> None:
        skills = get_bundled_skills()
        assert isinstance(skills, list)
        assert len(skills) > 0
        assert all("name" in s for s in skills)
        assert all("version" in s for s in skills)
        assert all(s["source"] == "bundled" for s in skills)

    def test_includes_jcli_config_skill(self) -> None:
        skills = get_bundled_skills()
        names = [s["name"] for s in skills]
        assert "jcli-config" in names


# ==================================================================
# get_installed_skills
# ==================================================================


class TestGetInstalledSkills:
    def test_returns_empty_when_dir_not_exists(self, temp_install_dir: Path) -> None:
        skills = get_installed_skills(temp_install_dir)
        assert skills == []

    def test_returns_installed_skills(self, temp_install_dir: Path) -> None:
        temp_install_dir.mkdir(parents=True)
        skill_dir = temp_install_dir / "test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("---\nname: test-skill\nversion: 1.0.0\n---\n# Test")

        skills = get_installed_skills(temp_install_dir)
        assert len(skills) == 1
        assert skills[0]["name"] == "test-skill"
        assert skills[0]["source"] == "installed"


# ==================================================================
# find_skill_dir
# ==================================================================


class TestFindSkillDir:
    def test_finds_by_directory_name(self) -> None:
        result = find_skill_dir("config")
        assert result is not None
        assert result.name == "config"
        assert result.exists()

    def test_finds_by_frontmatter_name(self) -> None:
        result = find_skill_dir("jcli-config")
        assert result is not None
        assert result.name == "config"
        assert result.exists()

    def test_returns_none_when_not_found(self) -> None:
        result = find_skill_dir("nonexistent-skill")
        assert result is None


# ==================================================================
# CLI: skills list
# ==================================================================


class TestSkillsListCommand:
    def test_lists_bundled_skills(self, runner: CliRunner) -> None:
        result = runner.invoke(skills_group, ["list", "--bundled"])
        assert result.exit_code == 0
        assert "Jcli Skills" in result.output
        assert "jcli-config" in result.output

    def test_lists_installed_skills(self, runner: CliRunner, temp_install_dir: Path) -> None:
        temp_install_dir.mkdir(parents=True)
        skill_dir = temp_install_dir / "test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("---\nname: test-skill\nversion: 1.0.0\n---\n# Test")

        result = runner.invoke(skills_group, ["list", "--installed", "--dir", str(temp_install_dir)])
        assert result.exit_code == 0
        assert "test-skill" in result.output


# ==================================================================
# CLI: skills install
# ==================================================================


class TestSkillsInstallCommand:
    def test_installs_skill(self, runner: CliRunner, temp_install_dir: Path) -> None:
        result = runner.invoke(
            skills_group,
            ["install", "jcli-config", "--dir", str(temp_install_dir)]
        )
        assert result.exit_code == 0
        assert "installed" in result.output.lower()

        # Verify symlink exists
        skill_link = temp_install_dir / "jcli-config"
        assert skill_link.exists()
        assert skill_link.is_symlink()

    def test_fails_when_not_found(self, runner: CliRunner, temp_install_dir: Path) -> None:
        result = runner.invoke(
            skills_group,
            ["install", "nonexistent-skill", "--dir", str(temp_install_dir)]
        )
        assert result.exit_code != 0

    def test_fails_when_already_installed(self, runner: CliRunner, temp_install_dir: Path) -> None:
        # Install once
        runner.invoke(
            skills_group,
            ["install", "jcli-config", "--dir", str(temp_install_dir)]
        )

        # Try to install again
        result = runner.invoke(
            skills_group,
            ["install", "jcli-config", "--dir", str(temp_install_dir)]
        )
        assert result.exit_code != 0
        assert "already installed" in result.output.lower()

    def test_force_overwrites(self, runner: CliRunner, temp_install_dir: Path) -> None:
        # Install once
        runner.invoke(
            skills_group,
            ["install", "jcli-config", "--dir", str(temp_install_dir)]
        )

        # Force install again
        result = runner.invoke(
            skills_group,
            ["install", "jcli-config", "--force", "--dir", str(temp_install_dir)]
        )
        assert result.exit_code == 0


# ==================================================================
# CLI: skills uninstall
# ==================================================================


class TestSkillsUninstallCommand:
    def test_uninstalls_skill(self, runner: CliRunner, temp_install_dir: Path) -> None:
        # Install first
        runner.invoke(
            skills_group,
            ["install", "jcli-config", "--dir", str(temp_install_dir)]
        )

        # Uninstall
        result = runner.invoke(
            skills_group,
            ["uninstall", "jcli-config", "--dir", str(temp_install_dir)]
        )
        assert result.exit_code == 0
        assert "uninstalled" in result.output.lower()

        # Verify symlink removed
        skill_link = temp_install_dir / "jcli-config"
        assert not skill_link.exists()

    def test_fails_when_not_installed(self, runner: CliRunner, temp_install_dir: Path) -> None:
        result = runner.invoke(
            skills_group,
            ["uninstall", "nonexistent-skill", "--dir", str(temp_install_dir)]
        )
        assert result.exit_code != 0


# ==================================================================
# CLI: skills get
# ==================================================================


class TestSkillsGetCommand:
    def test_gets_bundled_skill(self, runner: CliRunner) -> None:
        result = runner.invoke(skills_group, ["get", "jcli-config"])
        assert result.exit_code == 0
        assert "jcli-config" in result.output
        assert "1.0.0" in result.output

    def test_fails_when_not_found(self, runner: CliRunner) -> None:
        result = runner.invoke(skills_group, ["get", "nonexistent-skill"])
        assert result.exit_code != 0
