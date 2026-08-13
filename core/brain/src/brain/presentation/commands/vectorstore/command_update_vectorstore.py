# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `update-vectorstore` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="update-vectorstore",
    domain="vectorstore",
    help="Incrementally update modified memory files in the ChromaDB vector store.",
    arguments=[
        ArgumentSchema(
            flags=["--json"], action="store_true", help="Output results as JSON."
        ),
    ],
    description="Incrementally index modified memory files into the ChromaDB vector store.",
    stdin=(),
    examples=("py {LOCAL_BRAIN_SCRIPT} update-vectorstore --json",),
    output=("Updated-file and vector-count summary.",),
    exit_codes=("0: incremental update completed.", "1: indexing or storage failure."),
    safeguards=(
        "Processes only detected changes; existing unrelated vectors remain intact.",
    ),
    notes=("Run rebuild-vectorstore when collection contents must be reset.",),
)
