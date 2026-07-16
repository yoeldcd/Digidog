# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `write-diary` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="write-diary",
    domain="diary",
    help="Create or update an entry in the diary domain.",
    arguments=[
        ArgumentSchema(flags=["-d", "--datetime"], required=False, help="The entry timestamp in format DD-MM-YYYY HH:MM:SS (defaults to current local time)."),
        ArgumentSchema(flags=["-t", "--title"], required=True, help="The title of the diary entry."),
        ArgumentSchema(flags=["-tx", "--text"], required=False, help="The diary entry text content."),
        ArgumentSchema(flags=["body"], nargs="?", default=None, help="The diary entry text content (compact positional form)."),
    ],
)
