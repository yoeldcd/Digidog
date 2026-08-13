# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `read-log` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="read-log",
    domain="logs",
    help="Read workspace log entries for a specific date.",
    description="Read one log entry by its exact timestamp and print its stored fields.",
    stdin=("No stdin is read; provide the entry timestamp as an argument.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} read-log 2026-01-01T00:00:00 --json",),
    output=(
        "Prints the matching entry fields; --json emits the entry as structured data.",
    ),
    exit_codes=(
        "0: entry found and displayed.",
        "2: timestamp is invalid or no matching entry exists.",
    ),
    safeguards=("The command is read-only and requires an exact timestamp match.",),
    notes=(
        "Timestamp formats accepted by the log store include DD-MM-YYYY HH:mm am/pm.",
    ),
    arguments=[
        ArgumentSchema(
            flags=["-d", "--datetime"],
            required=False,
            help="The date to read in format DD-MM-YYYY or YYYY-MM-DD (defaults to current local date).",
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
            help="The date to read in format DD-MM-YYYY or YYYY-MM-DD (compact positional form).",
        ),
    ],
)
