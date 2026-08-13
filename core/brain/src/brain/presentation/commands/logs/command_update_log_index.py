# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `update-log-index` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="update-log-index",
    domain="logs",
    help="Import raw workspace logs into SQLite, archive originals, and refresh the DB log index.",
    description="Rebuild the log index from current log files and persist the refreshed index metadata.",
    stdin=("No stdin is read; indexing scope is determined by command options.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} update-log-index --json",),
    output=(
        "Reports the number of indexed entries and the resulting index timestamp.",
    ),
    exit_codes=(
        "0: index rebuilt.",
        "2: index options are invalid or a log file cannot be read.",
    ),
    safeguards=(
        "Existing log entries are read and indexed; source log contents are not rewritten.",
    ),
    notes=(
        "Run after manual log-file changes so log-index reflects the current files.",
    ),
    arguments=[
        ArgumentSchema(
            flags=["--fix"],
            action="store_true",
            help="Also import previous .log and legacy dated .md logs into SQLite before archiving.",
        ),
        ArgumentSchema(
            flags=["mode"],
            nargs="?",
            default=None,
            help="Use 'fix' to import previous .log and legacy dated .md logs too.",
        ),
    ],
)
