# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `list-profiles` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="list-profiles",
    domain="profiles",
    help="List available agent profiles and show how to read a complete profile.",
    arguments=[
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Print machine-readable profile names."),
    ],
)
