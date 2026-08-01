"""Centralized CLI helpers.

v2 only needs the output-formatter helper (used by the cliyard command
plugins, e.g. ``specs/plugins/jcli_commands.py``).  The v1 ``get_client``
helper was removed together with the legacy hand-written command modules
(``jcli/plugins/``).
"""

from __future__ import annotations

import click

from jcli.sdk.output import OutputFormatter


def get_formatter(ctx: click.Context) -> OutputFormatter:
    """Return an ``OutputFormatter`` matching the ``--format`` flag."""
    obj = ctx.obj or {}
    fmt = obj.get("format", "table")

    return OutputFormatter(format_type=fmt)
