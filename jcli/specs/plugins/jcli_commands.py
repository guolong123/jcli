"""Top-level command plugins for jcli 2.0: skills, completion.

Migrated verbatim from jcli v1:

* ``skills``  — jcli/plugins/skills.py
* ``completion`` — jcli/cli.py ``add_completion_command``

Each group is registered as a cliyard command plugin
(``@register_command``), so ``create_cli`` attaches it to the top-level
Click group.  Command semantics and output formats are unchanged from v1.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import click

from cliyard.plugin import register_command

from jcli.cli_helpers import get_formatter


# =====================================================================
# Skills commands (verbatim from jcli/plugins/skills.py)
# =====================================================================

# Bundled skills directory (ships with jcli package):
# <repo-root>/jcli/skills/jcli/*  — this plugin lives in <repo-root>/jcli/specs/plugins/
BUNDLED_SKILLS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "jcli" / "skills" / "jcli"
)

# Default install directory for opencode
DEFAULT_INSTALL_DIR = Path.home() / ".config" / "opencode" / "skills"

# SKILL.md frontmatter pattern
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_skill_metadata(skill_dir: Path) -> dict[str, Any]:
    """Parse SKILL.md frontmatter to extract metadata.

    Returns dict with keys: name, version, description, allowed_tools, path
    """
    skill_md = skill_dir / "SKILL.md"
    metadata: dict[str, Any] = {
        "name": skill_dir.name,
        "version": "",
        "description": "",
        "allowed_tools": [],
        "path": str(skill_dir),
    }

    if not skill_md.exists():
        return metadata

    try:
        content = skill_md.read_text(encoding="utf-8")
    except OSError:
        return metadata

    # Extract frontmatter
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        return metadata

    frontmatter = match.group(1)

    # Simple YAML parsing without pyyaml dependency
    lines = frontmatter.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("#"):
            i += 1
            continue

        if line.startswith("name:"):
            metadata["name"] = line.split(":", 1)[1].strip().strip("'\"")
        elif line.startswith("version:"):
            metadata["version"] = line.split(":", 1)[1].strip().strip("'\"")
        elif line.startswith("description:"):
            desc = line.split(":", 1)[1].strip().strip("'\"")
            if desc in ("|", ">", ""):
                # YAML block scalar: collect following indented lines
                parts = []
                j = i + 1
                while j < len(lines) and (
                    lines[j].startswith(" ") or lines[j].startswith("\t")
                ):
                    parts.append(lines[j].strip())
                    j += 1
                if parts:
                    desc = " ".join(parts)
                    i = j - 1  # continue after the block scalar
            metadata["description"] = desc
        elif line.startswith("- ") and "allowed-tools" in frontmatter:
            tool = line[2:].strip().strip("'\"")
            metadata["allowed_tools"].append(tool)
        i += 1

    return metadata


def _is_jcli_skill(metadata: dict[str, Any]) -> bool:
    """Return True if the skill belongs to jcli.

    A skill is considered jcli's own when:
    - it is a symlink into the bundled skills directory
      (``source == "bundled (symlink)"``), or
    - its name starts with the ``jcli-`` prefix, or
    - its path contains a ``jcli`` path segment (e.g. inside BUNDLED_SKILLS_DIR).
    """
    if metadata.get("source") == "bundled (symlink)":
        return True
    if str(metadata.get("name", "")).startswith("jcli-"):
        return True
    if "jcli" in Path(str(metadata.get("path", ""))).parts:
        return True
    return False


def get_bundled_skills() -> list[dict[str, Any]]:
    """Get all bundled skills from the skills directory."""
    skills = []

    if not BUNDLED_SKILLS_DIR.exists():
        return skills

    for skill_dir in sorted(BUNDLED_SKILLS_DIR.iterdir()):
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            metadata = parse_skill_metadata(skill_dir)
            metadata["source"] = "bundled"
            skills.append(metadata)

    return skills


def get_installed_skills(install_dir: Path | None = None) -> list[dict[str, Any]]:
    """Get all installed skills from the install directory."""
    target_dir = install_dir or DEFAULT_INSTALL_DIR
    skills = []

    if not target_dir.exists():
        return skills

    for skill_dir in sorted(target_dir.iterdir()):
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            metadata = parse_skill_metadata(skill_dir)
            metadata["source"] = "installed"
            # Check if it's a symlink to bundled
            if skill_dir.is_symlink():
                real_path = skill_dir.resolve()
                if str(BUNDLED_SKILLS_DIR) in str(real_path):
                    metadata["source"] = "bundled (symlink)"
            skills.append(metadata)

    return skills


def find_skill_dir(name: str) -> Path | None:
    """Find a bundled skill directory by name or frontmatter name."""
    direct_path = BUNDLED_SKILLS_DIR / name
    if direct_path.exists() and direct_path.is_dir():
        return direct_path

    for skill_dir in BUNDLED_SKILLS_DIR.iterdir():
        if skill_dir.is_dir():
            metadata = parse_skill_metadata(skill_dir)
            if metadata["name"] == name:
                return skill_dir

    return None


def install_skill(
    name: str,
    install_dir: Path | None = None,
    force: bool = False,
) -> bool:
    """Install a skill by creating a symlink.

    Returns True if successful, False otherwise.
    """
    target_dir = install_dir or DEFAULT_INSTALL_DIR

    # Find the bundled skill
    skill_source = find_skill_dir(name)
    if not skill_source:
        raise click.ClickException(f"Skill '{name}' not found in bundled skills.")

    skill_dest = target_dir / name

    # Path.exists() is False for a broken symlink; is_symlink() catches it
    if skill_dest.exists() or skill_dest.is_symlink():
        if force:
            # Remove existing
            if skill_dest.is_symlink():
                skill_dest.unlink()
            else:
                raise click.ClickException(
                    f"Skill '{name}' already installed at {skill_dest}. "
                    "Use --force to overwrite."
                )
        else:
            raise click.ClickException(
                f"Skill '{name}' already installed at {skill_dest}. "
                "Use --force to overwrite."
            )

    # Create install directory if needed
    target_dir.mkdir(parents=True, exist_ok=True)

    # Create symlink
    skill_dest.symlink_to(skill_source)
    return True


def uninstall_skill(name: str, install_dir: Path | None = None) -> bool:
    """Uninstall a skill by removing the symlink/directory.

    Returns True if successful, False otherwise.
    """
    target_dir = install_dir or DEFAULT_INSTALL_DIR
    skill_path = target_dir / name

    # Path.exists() is False for a broken symlink; is_symlink() catches it
    if not skill_path.exists() and not skill_path.is_symlink():
        raise click.ClickException(f"Skill '{name}' not found in {target_dir}.")

    if skill_path.is_symlink():
        skill_path.unlink()
    else:
        raise click.ClickException(
            f"Skill '{name}' is not a symlink. "
            "Manual removal required for non-symlinked skills."
        )

    return True


@click.group("skills", help="Manage jcli skills (list, install, uninstall).")
def skills_group() -> None:
    """Skills management commands."""


@skills_group.command("list")
@click.option("--installed", "-i", is_flag=True, help="Show only installed skills.")
@click.option("--bundled", "-b", is_flag=True, help="Show only bundled skills.")
@click.option("--dir", "install_dir", type=click.Path(exists=False), help="Custom install directory.")
@click.pass_context
def skills_list_cmd(ctx: click.Context, installed: bool, bundled: bool, install_dir: str | None) -> None:
    """List all available skills."""
    fmt = get_formatter(ctx)
    target_dir = Path(install_dir) if install_dir else DEFAULT_INSTALL_DIR

    skills_to_show = []

    if installed and bundled:
        # Both flags explicitly given: bundled + jcli installed (dedup by name)
        seen: set[str] = set()
        for skill in get_bundled_skills():
            skills_to_show.append(skill)
            seen.add(skill["name"])
        for skill in get_installed_skills(target_dir):
            if _is_jcli_skill(skill) and skill["name"] not in seen:
                skills_to_show.append(skill)
                seen.add(skill["name"])
    elif installed:
        # Only jcli installed skills
        skills_to_show.extend(
            s for s in get_installed_skills(target_dir) if _is_jcli_skill(s)
        )
    elif bundled:
        # Only bundled skills
        skills_to_show.extend(get_bundled_skills())
    else:
        # Default: only bundled (jcli's own skills)
        skills_to_show.extend(get_bundled_skills())

    if not skills_to_show:
        fmt.print_info("No skills found.")
        return

    headers = ["Name", "Version", "Description", "Source"]
    rows = [
        [
            s.get("name", ""),
            s.get("version", "-"),
            s.get("description", "")[:50] + ("..." if len(s.get("description", "")) > 50 else ""),
            s.get("source", ""),
        ]
        for s in skills_to_show
    ]
    fmt.print_table(headers, rows, title="Jcli Skills")


@skills_group.command("install")
@click.argument("name", required=False)
@click.option("--all", "-a", "install_all", is_flag=True, help="Install all bundled skills.")
@click.option("--force", "-f", is_flag=True, help="Force install (overwrite existing).")
@click.option("--dir", "install_dir", type=click.Path(exists=False), help="Custom install directory.")
@click.pass_context
def skills_install_cmd(ctx: click.Context, name: str | None, install_all: bool, force: bool, install_dir: str | None) -> None:
    """Install a skill.

    NAME is the skill name to install (from bundled skills).
    Use -a/--all to install all bundled skills.
    """
    fmt = get_formatter(ctx)
    target_dir = Path(install_dir) if install_dir else DEFAULT_INSTALL_DIR

    if not name and not install_all:
        raise click.UsageError("Must specify either NAME or -a/--all")

    if install_all:
        bundled = get_bundled_skills()
        success_count = 0
        skip_count = 0
        fail_count = 0

        for skill in bundled:
            skill_name = skill["name"]
            try:
                install_skill(skill_name, target_dir, force)
                fmt.print_success(f"Skill '{skill_name}' installed")
                success_count += 1
            except click.ClickException as exc:
                if "already installed" in str(exc):
                    fmt.print_info(f"Skill '{skill_name}' already installed, skipping")
                    skip_count += 1
                else:
                    fmt.print_error(f"Skill '{skill_name}': {exc}")
                    fail_count += 1

        fmt.console.print(f"\n[bold]Summary:[/bold] {success_count} installed, {skip_count} skipped, {fail_count} failed")
        return

    try:
        install_skill(name, target_dir, force)
    except click.ClickException:
        raise
    except Exception as exc:
        fmt.print_error(f"Failed to install skill '{name}': {exc}")
        raise SystemExit(1) from exc

    fmt.print_success(f"Skill '{name}' installed to {target_dir / name}")


@skills_group.command("uninstall")
@click.argument("name")
@click.option("--dir", "install_dir", type=click.Path(exists=False), help="Custom install directory.")
@click.pass_context
def skills_uninstall_cmd(ctx: click.Context, name: str, install_dir: str | None) -> None:
    """Uninstall a skill.

    NAME is the skill name to uninstall.
    """
    fmt = get_formatter(ctx)
    target_dir = Path(install_dir) if install_dir else DEFAULT_INSTALL_DIR

    try:
        uninstall_skill(name, target_dir)
    except click.ClickException:
        raise
    except Exception as exc:
        fmt.print_error(f"Failed to uninstall skill '{name}': {exc}")
        raise SystemExit(1) from exc

    fmt.print_success(f"Skill '{name}' uninstalled from {target_dir}")


@skills_group.command("get")
@click.argument("name")
@click.option("--installed", "-i", is_flag=True, help="Get from installed skills.")
@click.option("--dir", "install_dir", type=click.Path(exists=False), help="Custom install directory.")
@click.pass_context
def skills_get_cmd(ctx: click.Context, name: str, installed: bool, install_dir: str | None) -> None:
    """Show skill details and SKILL.md content."""
    fmt = get_formatter(ctx)
    target_dir = Path(install_dir) if install_dir else DEFAULT_INSTALL_DIR

    if installed:
        skill_dir = target_dir / name
    else:
        skill_dir = find_skill_dir(name)

    if not skill_dir or not skill_dir.exists():
        fmt.print_error(f"Skill '{name}' not found.")
        raise SystemExit(1)

    # Read and display SKILL.md
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        fmt.print_error(f"Skill '{name}' does not have a SKILL.md file.")
        raise SystemExit(1)

    try:
        content = skill_md.read_text(encoding="utf-8")
    except OSError as exc:
        fmt.print_error(f"Failed to read SKILL.md: {exc}")
        raise SystemExit(1) from exc

    # Print metadata
    metadata = parse_skill_metadata(skill_dir)
    fmt.console.print(f"\n[bold]Skill:[/bold] {metadata['name']}")
    if metadata["version"]:
        fmt.console.print(f"[bold]Version:[/bold] {metadata['version']}")
    if metadata["description"]:
        fmt.console.print(f"[bold]Description:[/bold] {metadata['description']}")
    fmt.console.print(f"[bold]Path:[/bold] {metadata['path']}")
    fmt.console.print("\n" + "=" * 60 + "\n")

    # Print content
    fmt.console.print(content)


# =====================================================================
# Completion command (verbatim from jcli/cli.py add_completion_command)
# =====================================================================


def build_completion_group(cli: click.Group) -> click.Group:
    """Build the ``completion show`` group attached to *cli*."""
    from click.shell_completion import BashComplete, FishComplete, ZshComplete

    @click.group()
    def completion() -> None:
        """Shell completion support for jcli."""

    @completion.command()
    @click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
    def show(shell: str) -> None:
        """Output shell completion script for the specified shell."""
        shell_cls = {"bash": BashComplete, "zsh": ZshComplete, "fish": FishComplete}
        complete = shell_cls[shell](cli, {}, "jcli", "_JCLI_COMPLETE")
        click.echo(complete.source(), nl=False)

    cli.add_command(completion)
    return completion


# =====================================================================
# cliyard command plugin registration
# =====================================================================


@register_command("skills")
def _register_skills(cli: click.Group, ctx: Any) -> None:
    """Attach the skills command group to the top-level CLI."""
    cli.add_command(skills_group)


@register_command("completion")
def _register_completion(cli: click.Group, ctx: Any) -> None:
    """Attach the completion command group to the top-level CLI."""
    build_completion_group(cli)
