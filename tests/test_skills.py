"""Tests for jcli skills commands — skills management commands.

jcli 2.0 mapping (v1 → v2):
- v1 ``jcli/plugins/skills.py`` was removed during the v1 legacy cleanup.
- The ``skills`` CLI command group and its helpers now live in
  ``jcli/specs/plugins/jcli_commands.py`` (cliyard command plugin).  Since
  ``jcli/specs/`` is not a Python package, the module is loaded via importlib so
  this file still tests the real v2 implementation.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from click.testing import CliRunner

# Load the v2 skills implementation from jcli/specs/plugins/jcli_commands.py.
_JCLI_COMMANDS_PATH = (
    Path(__file__).resolve().parent.parent / "jcli" / "specs" / "plugins" / "jcli_commands.py"
)
_spec = importlib.util.spec_from_file_location("jcli_commands", _JCLI_COMMANDS_PATH)
assert _spec is not None and _spec.loader is not None
jcli_commands = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(jcli_commands)

skills_group = jcli_commands.skills_group
get_bundled_skills = jcli_commands.get_bundled_skills
get_installed_skills = jcli_commands.get_installed_skills
parse_skill_metadata = jcli_commands.parse_skill_metadata
find_skill_dir = jcli_commands.find_skill_dir
BUNDLED_SKILLS_DIR = jcli_commands.BUNDLED_SKILLS_DIR
DEFAULT_INSTALL_DIR = jcli_commands.DEFAULT_INSTALL_DIR


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

    def test_includes_jcli_auth_skill(self) -> None:
        skills = get_bundled_skills()
        names = [s["name"] for s in skills]
        assert "jcli-auth" in names


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
        result = find_skill_dir("auth")
        assert result is not None
        assert result.name == "auth"
        assert result.exists()

    def test_finds_by_frontmatter_name(self) -> None:
        result = find_skill_dir("jcli-auth")
        assert result is not None
        assert result.name == "auth"
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
        assert "jcli-auth" in result.output

    def test_default_list_shows_only_jcli_skills(self, runner: CliRunner) -> None:
        result = runner.invoke(skills_group, ["list"])
        assert result.exit_code == 0
        assert "jcli-auth" in result.output
        assert "audit-log-analysis" not in result.output
        assert "ketacli-" not in result.output
        assert "lark-" not in result.output

    def test_lists_installed_skills(self, runner: CliRunner, temp_install_dir: Path) -> None:
        temp_install_dir.mkdir(parents=True)
        skill_dir = temp_install_dir / "jcli-test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("---\nname: jcli-test-skill\nversion: 1.0.0\n---\n# Test")

        result = runner.invoke(skills_group, ["list", "--installed", "--dir", str(temp_install_dir)])
        assert result.exit_code == 0
        assert "jcli-test-skill" in result.output


# ==================================================================
# CLI: skills install
# ==================================================================


class TestSkillsInstallCommand:
    def test_installs_skill(self, runner: CliRunner, temp_install_dir: Path) -> None:
        result = runner.invoke(
            skills_group,
            ["install", "jcli-auth", "--dir", str(temp_install_dir)]
        )
        assert result.exit_code == 0
        assert "installed" in result.output.lower()

        # Verify symlink exists
        skill_link = temp_install_dir / "jcli-auth"
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
            ["install", "jcli-auth", "--dir", str(temp_install_dir)]
        )

        # Try to install again
        result = runner.invoke(
            skills_group,
            ["install", "jcli-auth", "--dir", str(temp_install_dir)]
        )
        assert result.exit_code != 0
        assert "already installed" in result.output.lower()

    def test_force_overwrites(self, runner: CliRunner, temp_install_dir: Path) -> None:
        # Install once
        runner.invoke(
            skills_group,
            ["install", "jcli-auth", "--dir", str(temp_install_dir)]
        )

        # Force install again
        result = runner.invoke(
            skills_group,
            ["install", "jcli-auth", "--force", "--dir", str(temp_install_dir)]
        )
        assert result.exit_code == 0

    def test_force_overwrites_broken_symlink(self, runner: CliRunner, temp_install_dir: Path) -> None:
        # Create a broken symlink (target does not exist)
        temp_install_dir.mkdir(parents=True)
        skill_link = temp_install_dir / "jcli-auth"
        skill_link.symlink_to(temp_install_dir / "nonexistent-target")
        assert skill_link.is_symlink()
        assert not skill_link.exists()

        # Force install over the broken symlink
        result = runner.invoke(
            skills_group,
            ["install", "jcli-auth", "--force", "--dir", str(temp_install_dir)]
        )
        assert result.exit_code == 0

        # Broken symlink replaced with a working symlink to the bundled skill
        assert skill_link.is_symlink()
        assert skill_link.exists()
        assert (skill_link / "SKILL.md").exists()


# ==================================================================
# CLI: skills uninstall
# ==================================================================


class TestSkillsUninstallCommand:
    def test_uninstalls_skill(self, runner: CliRunner, temp_install_dir: Path) -> None:
        # Install first
        runner.invoke(
            skills_group,
            ["install", "jcli-auth", "--dir", str(temp_install_dir)]
        )

        # Uninstall
        result = runner.invoke(
            skills_group,
            ["uninstall", "jcli-auth", "--dir", str(temp_install_dir)]
        )
        assert result.exit_code == 0
        assert "uninstalled" in result.output.lower()

        # Verify symlink removed
        skill_link = temp_install_dir / "jcli-auth"
        assert not skill_link.exists()

    def test_fails_when_not_installed(self, runner: CliRunner, temp_install_dir: Path) -> None:
        result = runner.invoke(
            skills_group,
            ["uninstall", "nonexistent-skill", "--dir", str(temp_install_dir)]
        )
        assert result.exit_code != 0

    def test_uninstalls_broken_symlink(self, runner: CliRunner, temp_install_dir: Path) -> None:
        # Create a broken symlink (target does not exist)
        temp_install_dir.mkdir(parents=True)
        skill_link = temp_install_dir / "jcli-auth"
        skill_link.symlink_to(temp_install_dir / "nonexistent-target")
        assert skill_link.is_symlink()
        assert not skill_link.exists()

        result = runner.invoke(
            skills_group,
            ["uninstall", "jcli-auth", "--dir", str(temp_install_dir)]
        )
        assert result.exit_code == 0
        assert not skill_link.is_symlink()


# ==================================================================
# CLI: skills get
# ==================================================================


class TestSkillsGetCommand:
    def test_gets_bundled_skill(self, runner: CliRunner) -> None:
        result = runner.invoke(skills_group, ["get", "jcli-auth"])
        assert result.exit_code == 0
        assert "jcli-auth" in result.output
        assert "1.0.0" in result.output

    def test_fails_when_not_found(self, runner: CliRunner) -> None:
        result = runner.invoke(skills_group, ["get", "nonexistent-skill"])
        assert result.exit_code != 0
