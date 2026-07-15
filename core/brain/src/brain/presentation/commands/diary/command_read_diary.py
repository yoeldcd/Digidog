"""Command metadata for the `read-diary` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="read-diary",
    domain="diary",
    help="Read entries from the diary domain.",
    arguments=[
        ArgumentSchema(flags=["-d", "--datetime"], required=False, help="The date to read in format DD-MM-YYYY (defaults to current local date)."),
        ArgumentSchema(flags=["--time"], required=False, help="Optional exact entry time in HH:MM."),
        ArgumentSchema(flags=["-l", "--limit"], type="int", default=None, help="Limit the number of lines printed."),
        ArgumentSchema(flags=["date"], nargs="?", default=None, help="The date to read in format DD-MM-YYYY (compact positional form)."),
    ],
)
