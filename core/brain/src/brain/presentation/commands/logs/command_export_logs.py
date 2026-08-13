# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `export-logs` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="export-logs",
    domain="logs",
    help="Export DB-backed workspace logs for stdout consumers or migration artifacts.",
    description="Export the complete agent log collection to a JSON file or stdout destination.",
    stdin=("No stdin is read; select the destination with command options.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} export-logs --output logs.json",),
    output=(
        "Writes serialized log entries to the requested output path and reports export counts.",
    ),
    exit_codes=(
        "0: logs exported.",
        "2: destination or export arguments are invalid, or logs cannot be read.",
    ),
    safeguards=(
        "Export is read-only for log records and does not alter timestamps or entries.",
    ),
    notes=(
        "Use --output to choose a file; --json controls the command response format.",
    ),
    arguments=[
        ArgumentSchema(
            flags=["--stdout"],
            action="store_true",
            help="Export Markdown to stdout without writing files; this is the default target.",
        ),
        ArgumentSchema(
            flags=["--domain"],
            required=False,
            help="Optional log domain prefix for stdout export.",
        ),
        ArgumentSchema(
            flags=["--date"],
            required=False,
            help="Optional exact date filter in DD-MM-YYYY or YYYY-MM-DD.",
        ),
        ArgumentSchema(
            flags=["--time"],
            required=False,
            help="Optional exact time filter in HH:MM with optional am/pm.",
        ),
        ArgumentSchema(
            flags=["--from"],
            required=False,
            help="Optional inclusive lower date/timestamp bound.",
        ),
        ArgumentSchema(
            flags=["--to"],
            required=False,
            help="Optional inclusive upper date/timestamp bound.",
        ),
        ArgumentSchema(
            flags=["--files"],
            action="store_true",
            help="Migration only: export canonical .log.md files.",
        ),
        ArgumentSchema(
            flags=["--output"],
            required=False,
            help="Output directory for --files. Defaults to $agent/logs.",
        ),
        ArgumentSchema(
            flags=["--zip"],
            required=False,
            help="Output zip path for canonical log files.",
        ),
    ],
)
