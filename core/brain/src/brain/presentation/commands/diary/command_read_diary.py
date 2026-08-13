# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `read-diary` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="read-diary",
    domain="diary",
    help="Read entries from the diary domain.",
    arguments=[
        ArgumentSchema(
            flags=["-d", "--datetime"],
            required=False,
            help="The date to read in format DD-MM-YYYY (defaults to current local date).",
        ),
        ArgumentSchema(
            flags=["--time"], required=False, help="Optional exact entry time in HH:MM."
        ),
        ArgumentSchema(
            flags=["-l", "--limit"],
            type="int",
            default=None,
            help="Limit the number of lines printed.",
        ),
        ArgumentSchema(
            flags=["date"],
            nargs="?",
            default=None,
            help="The date to read in format DD-MM-YYYY (compact positional form).",
        ),
    ],
    description="Read diary entries, optionally filtered by date or timestamp.",
    stdin=(),
    examples=("py {LOCAL_BRAIN_SCRIPT} read-diary 27-06-2026",),
    output=("Matching diary entries are printed chronologically.",),
    exit_codes=("0: entries read", "1: invalid date or timestamp"),
    safeguards=("Read operations do not alter diary data.",),
    notes=("Omitting filters reads the current diary scope.",),
)
