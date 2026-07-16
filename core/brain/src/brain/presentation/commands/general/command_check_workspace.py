# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `check-workspace` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="check-workspace",
    domain="general",
    help="Validate workspace memory structure and nesting compliance.",
    arguments=[
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Print report as JSON."),
    ],
)
