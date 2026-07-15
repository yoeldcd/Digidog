"""Command metadata for the `create-brain` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="create-brain",
    domain="general",
    help="Create a local Brain consumer in a target workspace using core/core_cli.py. (e.g. create-brain <workspace-root>)",
    arguments=[
        ArgumentSchema(
            flags=["--workspace", "-w"],
            help="Target workspace root path.",
            required=False,
            type="str",
        ),
        ArgumentSchema(
            flags=["workspace_path"],
            help="Target workspace root path (compact positional form).",
            nargs="?",
            default=None,
        ),
        ArgumentSchema(
            flags=["--limit", "-l"],
            help="Limit the number of migrated files logged to the terminal.",
            type="int",
            default=10,
        ),
    ],
)
