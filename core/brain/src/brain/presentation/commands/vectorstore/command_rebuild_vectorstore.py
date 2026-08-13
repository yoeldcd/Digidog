# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `rebuild-vectorstore` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="rebuild-vectorstore",
    domain="vectorstore",
    help="Reset and completely index all memories in ChromaDB from scratch. (Destructive command, use update-vectorstore for incremental updates).",
    arguments=[
        ArgumentSchema(
            flags=["-y", "--yes"],
            action="store_true",
            help="Skip confirmation prompt for destructive rebuild.",
        ),
        ArgumentSchema(
            flags=["--json"], action="store_true", help="Output results as JSON."
        ),
    ],
    description="Reset and rebuild the complete ChromaDB memory index.",
    stdin=(),
    examples=("py {LOCAL_BRAIN_SCRIPT} rebuild-vectorstore --yes --json",),
    output=("Full-index rebuild summary.",),
    exit_codes=("0: index rebuilt.", "1: confirmation, indexing, or storage failure."),
    safeguards=("Requires --yes to skip the destructive confirmation prompt.",),
    notes=("This operation reindexes all supported memory sources.",),
)
