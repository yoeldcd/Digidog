# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `help` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="help",
    domain="general",
    help="Show memory store help.",
    arguments=[
        ArgumentSchema(flags=["topic"], nargs="?", default=None, help="Optional command name to inspect."),
        ArgumentSchema(flags=["--short"], action="store_true", help="Show only domains and command names."),
    ],
)
