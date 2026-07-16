# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `list-snippets` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="list-snippets",
    domain="snippets",
    help="Search or list reusable snippets in the configured agent directory.",
    arguments=[
        ArgumentSchema(flags=["-f", "--filter"], help="Optional filter to search in snippet names."),
        ArgumentSchema(flags=["query"], nargs="?", help="Optional keyword to search in snippet names."),
    ],
)
