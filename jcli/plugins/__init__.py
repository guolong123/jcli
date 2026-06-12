"""Jenkins CLI plugins - register all subcommands."""

import click

from jcli.plugins.build import register as register_build
from jcli.plugins.config import register as register_config
from jcli.plugins.credential import register as register_credential
from jcli.plugins.job import register as register_job
from jcli.plugins.node import register as register_node
from jcli.plugins.pipeline import register as register_pipeline
from jcli.plugins.plugin import register as register_plugin
from jcli.plugins.skills import register as register_skills
from jcli.plugins.system import register as register_system
from jcli.plugins.view import register as register_view


def register_commands(group: click.Group) -> None:
    """Register all plugin subcommands under the main CLI group."""
    register_build(group)
    register_config(group)
    register_credential(group)
    register_job(group)
    register_node(group)
    register_pipeline(group)
    register_plugin(group)
    register_skills(group)
    register_system(group)
    register_view(group)
