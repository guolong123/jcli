"""Jenkins CLI - Command line interface for managing Jenkins."""

import logging
import sys

import click

from jcli import __version__
from jcli.plugins import register_commands

logger = logging.getLogger("jcli")


@click.group()
@click.version_option(version=__version__, prog_name="jcli")
@click.option(
    "-f",
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["table", "json", "yaml"]),
    help="Output format.",
)
@click.option("-p", "--profile", default=None, help="Configuration profile name.")
@click.option("-s", "--server", default=None, help="Jenkins server URL.")
@click.option("-d", "--debug", is_flag=True, default=False, help="Enable debug output.")
@click.pass_context
def cli(ctx, output_format, profile, server, debug):
    """Jenkins CLI - Manage Jenkins from the command line."""
    ctx.ensure_object(dict)
    ctx.obj["format"] = output_format
    ctx.obj["profile"] = profile
    ctx.obj["server"] = server
    ctx.obj["debug"] = debug

    # Configure debug logging when --debug / -d is set
    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
            stream=sys.stderr,
        )
        logger.debug("Debug logging enabled")
    else:
        # Ensure WARNING+ level when not in debug mode
        logging.basicConfig(level=logging.WARNING, stream=sys.stderr)


# Register all plugin subcommands
register_commands(cli)


@click.group()
def completion():
    """Shell completion support for jcli."""
    pass


@completion.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def show(shell):
    """Output shell completion script for the specified shell."""
    from click.shell_completion import BashComplete, ZshComplete, FishComplete

    shell_cls = {"bash": BashComplete, "zsh": ZshComplete, "fish": FishComplete}
    complete = shell_cls[shell](cli, {}, "jcli", "_JCLI_COMPLETE")
    click.echo(complete.source(), nl=False)


cli.add_command(completion)


def main():
    """CLI entry point."""
    cli()


if __name__ == "__main__":
    main()
