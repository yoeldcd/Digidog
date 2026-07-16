# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `read-log` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="read-log",
    domain="logs",
    help="Read workspace log entries for a specific date.",
    arguments=[
        ArgumentSchema(flags=["-d", "--datetime"], required=False, help="The date to read in format DD-MM-YYYY or YYYY-MM-DD (defaults to current local date)."),
        ArgumentSchema(flags=["--time"], required=False, help="Optional exact entry time in HH:MM."),
        ArgumentSchema(flags=["-l", "--limit"], type="int", default=None, help="Limit the number of lines printed."),
        ArgumentSchema(flags=["date"], nargs="?", default=None, help="The date to read in format DD-MM-YYYY or YYYY-MM-DD (compact positional form)."),
    ],
)
