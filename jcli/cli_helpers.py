"""Centralized CLI helpers for creating JenkinsClient and OutputFormatter.

All plugin modules should import ``get_client`` and ``get_formatter`` from here
instead of implementing their own versions.  This ensures consistent behaviour
for ``--profile``, ``--server``, and ``--format`` across every subcommand.
"""

from __future__ import annotations

import logging

import click

from jcli.sdk.client import JenkinsClient
from jcli.sdk.config import Config
from jcli.sdk.output import OutputFormatter

logger = logging.getLogger(__name__)


def get_client(ctx: click.Context) -> JenkinsClient:
    """Return a cached ``JenkinsClient`` from the Click context.

    Resolution order:
    1. Re-use ``ctx.obj["client"]`` if already present (tests / caching).
    2. Load the config profile selected by ``--profile`` / ``$JCLI_PROFILE``.
    3. Override the profile URL with ``--server`` when provided.
    """
    obj = ctx.obj or {}

    # Allow pre-created client (used by tests and internal callers)
    if "client" in obj:
        return obj["client"]

    config = Config()
    config.load()

    profile_name = obj.get("profile") or config.get_active_profile_name()
    profile = config.get_profile(profile_name)

    url = obj.get("server") or profile["url"]
    username = profile["username"]
    token = profile["api_token"]

    client = JenkinsClient(base_url=url, username=username, token=token)
    logger.debug("Created JenkinsClient for %s (profile=%s)", url, profile_name)

    # Cache for subsequent calls within the same invocation
    obj["client"] = client
    return client


def get_formatter(ctx: click.Context) -> OutputFormatter:
    """Return an ``OutputFormatter`` matching the ``--format`` flag."""
    obj = ctx.obj or {}
    fmt = obj.get("format", "table")

    return OutputFormatter(format_type=fmt)
