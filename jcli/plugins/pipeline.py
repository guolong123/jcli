"""Jenkins Pipeline management commands."""

import click

from jcli.cli_helpers import get_client, get_formatter
from jcli.sdk.exceptions import (
    JenkinsAPIError,
    JenkinsAuthError,
    JenkinsConnectionError,
    JenkinsNotFoundError,
)
from jcli.sdk.pipeline import (
    get_pending_input,
    get_pipeline_log,
    get_pipeline_stages,
    validate_jenkinsfile,
)


@click.group("pipeline", help="Manage Jenkins pipelines.")
def pipeline_group():
    """Pipeline management commands."""


@pipeline_group.command("stages")
@click.argument("job_name")
@click.argument("build_number")
@click.pass_context
def stages(ctx, job_name, build_number):
    """List stages for a Pipeline build.

    JOB_NAME is the Pipeline job name.
    BUILD_NUMBER is the build number to query.
    """
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    try:
        result = get_pipeline_stages(client, job_name, build_number)
        fmt.print_json(result)
    except (JenkinsNotFoundError, JenkinsAuthError, JenkinsConnectionError, JenkinsAPIError) as exc:
        fmt.print_error(str(exc))


@pipeline_group.command("log")
@click.argument("job_name")
@click.argument("build_number")
@click.argument("node_id")
@click.pass_context
def log(ctx, job_name, build_number, node_id):
    """Get log output for a Pipeline step.

    JOB_NAME is the Pipeline job name.
    BUILD_NUMBER is the build number to query.
    NODE_ID is the flow node ID from stage/step info.
    """
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    try:
        result = get_pipeline_log(client, job_name, build_number, node_id)
        fmt.print_json(result)
    except (JenkinsNotFoundError, JenkinsAuthError, JenkinsConnectionError, JenkinsAPIError) as exc:
        fmt.print_error(str(exc))


@pipeline_group.command("validate")
@click.argument("file_path", type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def validate(ctx, file_path):
    """Validate a Jenkinsfile against the Jenkins server.

    FILE_PATH is the path to the Jenkinsfile to validate.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    client = get_client(ctx)
    fmt = get_formatter(ctx)

    result = validate_jenkinsfile(client, content)

    fmt.print_json(result)


@pipeline_group.command("pending")
@click.argument("job_name")
@click.argument("build_number")
@click.pass_context
def pending(ctx, job_name, build_number):
    """Show pending input actions for a Pipeline build.

    JOB_NAME is the Pipeline job name.
    BUILD_NUMBER is the build number to query.
    """
    client = get_client(ctx)
    fmt = get_formatter(ctx)

    try:
        result = get_pending_input(client, job_name, build_number)
        fmt.print_json(result)
    except (JenkinsNotFoundError, JenkinsAuthError, JenkinsConnectionError, JenkinsAPIError) as exc:
        fmt.print_error(str(exc))


def register(parent_group):
    """Register the pipeline subgroup under the parent Click group."""
    parent_group.add_command(pipeline_group)
