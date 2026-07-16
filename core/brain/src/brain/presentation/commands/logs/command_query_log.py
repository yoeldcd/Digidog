# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `query-log` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="query-log",
    domain="logs",
    help="Perform semantic similarity search on workspace logs. (e.g. query-log profiles.friend 'preamble scenes')",
    arguments=[
        ArgumentSchema(flags=["domain"], nargs="?", help="Log domain prefix to restrict search (optional)."),
        ArgumentSchema(flags=["query"], nargs="?", help="Text query to search semantically (required)."),
        ArgumentSchema(flags=["-l", "--limit"], type="int", default=5, help="Limit number of semantic matches (default: 5)."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Output results as JSON."),
    ],
)
