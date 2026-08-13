# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `query-log` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="query-log",
    domain="logs",
    help="Perform semantic similarity search on workspace logs. (e.g. query-log profiles.friend 'preamble scenes')",
    description="Search log entries for a text query across their stored fields.",
    stdin=(
        "No stdin is read; provide the search text and optional filters as arguments.",
    ),
    examples=('py {LOCAL_BRAIN_SCRIPT} query-log "release" --json',),
    output=(
        "Prints matching entries and their timestamps; --json emits the complete match set.",
    ),
    exit_codes=(
        "0: query completed, including zero matches.",
        "2: query text or filters are invalid, or logs cannot be read.",
    ),
    safeguards=(
        "Search is read-only and matches text in indexed entry content without changing records.",
    ),
    notes=("Queries are case-insensitive according to the log search implementation.",),
    arguments=[
        ArgumentSchema(
            flags=["domain"],
            nargs="?",
            help="Log domain prefix to restrict search (optional).",
        ),
        ArgumentSchema(
            flags=["query"],
            nargs="?",
            help="Text query to search semantically (required).",
        ),
        ArgumentSchema(
            flags=["-l", "--limit"],
            type="int",
            default=5,
            help="Limit log matches only; always-on policies are returned separately (default: 5).",
        ),
        ArgumentSchema(
            flags=["-j", "--json"], action="store_true", help="Output results as JSON."
        ),
    ],
)
