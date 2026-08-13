# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `log-index` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="log-index",
    domain="logs",
    help="Display the workspace logs index, optionally filtered by domain.",
    description="List the indexed log files and their recorded metadata.",
    stdin=("No stdin is read; filters and output format are selected with options.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} log-index --json",),
    output=(
        "Prints indexed paths, timestamps, and entry counts; --json emits the index records.",
    ),
    exit_codes=(
        "0: index listed.",
        "2: index filters are invalid or the index cannot be read.",
    ),
    safeguards=(
        "The command only reads index metadata and does not modify log files.",
    ),
    notes=("Use update-log-index to rebuild stale metadata before inspecting it.",),
    arguments=[
        ArgumentSchema(
            flags=["section"],
            nargs="?",
            help="Filter to show only a specific change domain (e.g. brain).",
        ),
    ],
)
