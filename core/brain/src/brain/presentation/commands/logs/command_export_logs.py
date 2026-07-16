# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `export-logs` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="export-logs",
    domain="logs",
    help="Export DB-backed workspace logs for stdout consumers or migration artifacts.",
    arguments=[
        ArgumentSchema(flags=["--stdout"], action="store_true", help="Export Markdown to stdout without writing files; this is the default target."),
        ArgumentSchema(flags=["--domain"], required=False, help="Optional log domain prefix for stdout export."),
        ArgumentSchema(flags=["--date"], required=False, help="Optional exact date filter in DD-MM-YYYY or YYYY-MM-DD."),
        ArgumentSchema(flags=["--time"], required=False, help="Optional exact time filter in HH:MM with optional am/pm."),
        ArgumentSchema(flags=["--from"], required=False, help="Optional inclusive lower date/timestamp bound."),
        ArgumentSchema(flags=["--to"], required=False, help="Optional inclusive upper date/timestamp bound."),
        ArgumentSchema(flags=["--files"], action="store_true", help="Migration only: export canonical .log.md files."),
        ArgumentSchema(flags=["--output"], required=False, help="Output directory for --files. Defaults to $agent/logs."),
        ArgumentSchema(flags=["--zip"], required=False, help="Output zip path for canonical log files."),
    ],
)
