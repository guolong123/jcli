"""Jenkins Job management commands."""

from __future__ import annotations

import click

from jcli.cli_helpers import get_client, get_formatter
from jcli.sdk.exceptions import JenkinsError, JenkinsNotFoundError
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


# ------------------------------------------------------------------
# Click group
# ------------------------------------------------------------------


@click.group("job", help="Manage Jenkins jobs.")
def job_group() -> None:
    """Job management commands."""


# ------------------------------------------------------------------
# list
# ------------------------------------------------------------------


@job_group.command("list")
@click.pass_context
def list_cmd(ctx: click.Context) -> None:
    """List all Jenkins jobs."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    try:
        jobs = list_jobs(client)
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1) from exc

    if not jobs:
        fmt.print_info("No jobs found.")
        return

    headers = ["Name", "URL", "Color"]
    rows = [[j.get("name", ""), j.get("url", ""), j.get("color", "")] for j in jobs]
    fmt.print_table(headers, rows, title="Jenkins Jobs")


# ------------------------------------------------------------------
# get
# ------------------------------------------------------------------


@job_group.command("get")
@click.argument("name")
@click.pass_context
def get_cmd(ctx: click.Context, name: str) -> None:
    """Show details for a specific job."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    try:
        job = get_job(client, name)
    except JenkinsNotFoundError:
        fmt.print_error(f"Job '{name}' not found.")
        raise SystemExit(1)
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1) from exc

    fmt.print_json(job)


# ------------------------------------------------------------------
# create
# ------------------------------------------------------------------


@job_group.command("create")
@click.argument("name")
@click.argument("config_file", type=click.Path(exists=True, dir_okay=False, readable=True), required=False)
@click.option("--type", "job_type", type=click.Choice(["freestyle", "pipeline"]), help="Job type (skip config_file).")
@click.option("--git-url", help="Git repository URL.")
@click.option("--git-branch", default="main", help="Git branch (default: main).")
@click.option("--description", default="", help="Job description.")
@click.option("--shell", help="Shell script to run (freestyle only).")
@click.option("--cron", help="Cron schedule for periodic build (freestyle only).")
@click.option("--jenkinsfile", default="Jenkinsfile", help="Jenkinsfile path (pipeline only).")
@click.option("--script", help="Inline Pipeline script (pipeline only).")
@click.pass_context
def create_cmd(
    ctx: click.Context,
    name: str,
    config_file: str | None,
    job_type: str | None,
    git_url: str | None,
    git_branch: str,
    description: str,
    shell: str | None,
    cron: str | None,
    jenkinsfile: str,
    script: str | None,
) -> None:
    """Create a new job from an XML configuration file or parameters.

    NAME is the name for the new job.
    CONFIG_FILE is the path to the XML file (optional if --type is specified).

    Examples:
      jcli job create myjob config.xml
      jcli job create myjob --type freestyle --git-url https://... --shell "make build"
      jcli job create mypipe --type pipeline --git-url https://... --jenkinsfile Jenkinsfile
      jcli job create mypipe --type pipeline --script "pipeline { agent any; stages { stage('build') { steps { echo 'hi' } } } }"
    """
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    try:
        if config_file:
            # XML file mode (backward compatible)
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config_xml = f.read()
            except OSError as exc:
                fmt.print_error(f"Cannot read config file '{config_file}': {exc}")
                raise SystemExit(1) from exc
        elif job_type:
            # Parameter mode
            from jcli.sdk.job_templates import generate_freestyle_xml, generate_pipeline_xml

            if job_type == "freestyle":
                config_xml = generate_freestyle_xml(
                    git_url=git_url or "",
                    git_branch=git_branch,
                    shell_script=shell or "",
                    description=description,
                    cron_schedule=cron or "",
                )
            else:
                config_xml = generate_pipeline_xml(
                    git_url=git_url or "",
                    git_branch=git_branch,
                    jenkinsfile_path=jenkinsfile,
                    description=description,
                    script=script or "",
                )
        else:
            raise click.UsageError("Must specify either CONFIG_FILE or --type")

        create_job(client, name, config_xml)
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1) from exc

    fmt.print_success(f"Job '{name}' created.")


# ------------------------------------------------------------------
# update
# ------------------------------------------------------------------


@job_group.command("update")
@click.argument("job_name")
@click.argument("config_file", type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def update_cmd(ctx: click.Context, job_name: str, config_file: str) -> None:
    """Update a job's configuration from an XML file.

    JOB_NAME is the name of the job to update.
    CONFIG_FILE is the path to the new XML configuration file.
    """
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config_xml = f.read()
    except OSError as exc:
        fmt.print_error(f"Cannot read config file '{config_file}': {exc}")
        raise SystemExit(1) from exc

    try:
        update_job_config(client, job_name, config_xml)
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1) from exc

    fmt.print_success(f"Job '{job_name}' updated.")


# ------------------------------------------------------------------
# delete
# ------------------------------------------------------------------


@job_group.command("delete")
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@click.pass_context
def delete_cmd(ctx: click.Context, name: str, yes: bool) -> None:
    """Delete a job.

    Prompts for confirmation unless --yes/-y is given.
    """
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    if not yes:
        confirm = input(f"Are you sure you want to delete job '{name}'? [y/N]: ")
        if confirm.lower() not in ("y", "yes"):
            fmt.print_info("Delete cancelled.")
            return

    try:
        delete_job(client, name)
    except JenkinsNotFoundError:
        fmt.print_error(f"Job '{name}' not found.")
        raise SystemExit(1)
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1) from exc

    fmt.print_success(f"Job '{name}' deleted.")


# ------------------------------------------------------------------
# copy
# ------------------------------------------------------------------


@job_group.command("copy")
@click.argument("from_name")
@click.argument("new_name")
@click.pass_context
def copy_cmd(ctx: click.Context, from_name: str, new_name: str) -> None:
    """Copy a job to a new name.

    FROM_NAME is the source job.
    NEW_NAME is the name for the copied job.
    """
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    try:
        copy_job(client, from_name, new_name)
    except JenkinsNotFoundError:
        fmt.print_error(f"Source job '{from_name}' not found.")
        raise SystemExit(1)
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1) from exc

    fmt.print_success(f"Job '{from_name}' copied to '{new_name}'.")


# ------------------------------------------------------------------
# rename
# ------------------------------------------------------------------


@job_group.command("rename")
@click.argument("old_name")
@click.argument("new_name")
@click.pass_context
def rename_job_cmd(ctx: click.Context, old_name: str, new_name: str) -> None:
    """Rename a job.

    OLD_NAME is the current name of the job.
    NEW_NAME is the new name to assign to the job.
    """
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    try:
        rename_job(client, old_name, new_name)
    except JenkinsNotFoundError:
        fmt.print_error(f"Job '{old_name}' not found.")
        raise SystemExit(1)
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1) from exc

    fmt.print_success(f"Job renamed from '{old_name}' to '{new_name}'.")


# ------------------------------------------------------------------
# enable / disable
# ------------------------------------------------------------------


@job_group.command("enable")
@click.argument("name")
@click.pass_context
def enable_cmd(ctx: click.Context, name: str) -> None:
    """Enable a disabled job."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    try:
        enable_job(client, name)
    except JenkinsNotFoundError:
        fmt.print_error(f"Job '{name}' not found.")
        raise SystemExit(1)
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1) from exc

    fmt.print_success(f"Job '{name}' enabled.")


@job_group.command("disable")
@click.argument("name")
@click.pass_context
def disable_cmd(ctx: click.Context, name: str) -> None:
    """Disable a job."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    try:
        disable_job(client, name)
    except JenkinsNotFoundError:
        fmt.print_error(f"Job '{name}' not found.")
        raise SystemExit(1)
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1) from exc

    fmt.print_success(f"Job '{name}' disabled.")


# ------------------------------------------------------------------
# config
# ------------------------------------------------------------------


@job_group.command("config")
@click.argument("name")
@click.pass_context
def config_cmd(ctx: click.Context, name: str) -> None:
    """Print the XML configuration of a job."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    try:
        xml_text = get_job_config(client, name)
    except JenkinsNotFoundError:
        fmt.print_error(f"Job '{name}' not found.")
        raise SystemExit(1)
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1) from exc

    fmt.console.print(xml_text)


# ------------------------------------------------------------------
# create-folder
# ------------------------------------------------------------------


@job_group.command("create-folder")
@click.argument("name")
@click.pass_context
def create_folder_cmd(ctx: click.Context, name: str) -> None:
    """Create a new folder."""
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    try:
        create_folder(client, name)
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1) from exc

    fmt.print_success(f"Folder '{name}' created.")


# ------------------------------------------------------------------
# delete-folder
# ------------------------------------------------------------------


@job_group.command("delete-folder")
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@click.pass_context
def delete_folder_cmd(ctx: click.Context, name: str, yes: bool) -> None:
    """Delete a folder and all its contents."""
    if not yes:
        click.confirm(f"Delete folder '{name}' and ALL its contents?", abort=True)

    client = get_client(ctx)
    fmt = get_formatter(ctx)

    try:
        delete_folder(client, name)
    except JenkinsError as exc:
        fmt.print_error(str(exc))
        raise SystemExit(1) from exc

    fmt.print_success(f"Folder '{name}' deleted.")


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------


def register(parent_group: click.Group) -> None:
    """Register the job subgroup under the parent Click group."""
    parent_group.add_command(job_group)
