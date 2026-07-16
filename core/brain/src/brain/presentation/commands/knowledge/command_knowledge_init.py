# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `knowledge-init` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="knowledge-init",
    domain="knowledge",
    help="Initialize the private knowledge graph runtime and SQLite schema.",
    arguments=[
        ArgumentSchema(
            flags=["--reset"],
            action="store_true",
            help="Delete and recreate the private knowledge database.",
        ),
        ArgumentSchema(
            flags=["--scope"],
            default="all",
            help="Knowledge DB scope: all, global, or local. Defaults to all.",
        ),
        ArgumentSchema(flags=["-y", "--yes"], action="store_true", help="Skip reset confirmation."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Output results as JSON."),
    ],
)
