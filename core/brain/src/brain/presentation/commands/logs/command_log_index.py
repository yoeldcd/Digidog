# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `log-index` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="log-index",
    domain="logs",
    help="Display the workspace logs index, optionally filtered by domain.",
    arguments=[
        ArgumentSchema(flags=["section"], nargs="?", help="Filter to show only a specific change domain (e.g. brain)."),
    ],
)
