# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `vectorstore-status` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="vectorstore-status",
    domain="vectorstore",
    help="Display ChromaDB configuration, active models, and memory vector statistics.",
    arguments=[
        ArgumentSchema(
            flags=["--json"], action="store_true", help="Output results as JSON."
        ),
    ],
    description="Report global ChromaDB configuration, models, and memory vector statistics.",
    stdin=(),
    examples=("py {LOCAL_BRAIN_SCRIPT} vectorstore-status --json",),
    output=("Vector-store configuration and aggregate statistics.",),
    exit_codes=("0: status read.", "1: vector store unavailable or unreadable."),
    safeguards=("Read-only inspection; no index mutation occurs.",),
    notes=("Use local-vectorstore-status for collection-specific local details.",),
)
