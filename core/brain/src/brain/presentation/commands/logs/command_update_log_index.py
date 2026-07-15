"""Command metadata for the `update-log-index` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="update-log-index",
    domain="logs",
    help="Import raw workspace logs into SQLite, archive originals, and refresh the DB log index.",
    arguments=[
        ArgumentSchema(flags=["--fix"], action="store_true", help="Also import previous .log and legacy dated .md logs into SQLite before archiving."),
        ArgumentSchema(flags=["mode"], nargs="?", default=None, help="Use 'fix' to import previous .log and legacy dated .md logs too."),
    ],
)
