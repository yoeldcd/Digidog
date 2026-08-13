# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `local-vectorstore-status` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="local-vectorstore-status",
    domain="vectorstore",
    help="Display ChromaDB configuration, collections, and vector statistics for the local workspace store.",
    arguments=[
        ArgumentSchema(
            flags=["--json"], action="store_true", help="Output results as JSON."
        ),
    ],
    description="Show local ChromaDB collections and vector counts for the workspace.",
    stdin=(),
    examples=("py {LOCAL_BRAIN_SCRIPT} local-vectorstore-status --json",),
    output=("Local store configuration, collections, and statistics.",),
    exit_codes=("0: status read.", "1: local vector store unavailable."),
    safeguards=("Read-only inspection; no vectors are changed.",),
    notes=("Use rebuild-local-vectorstore for a full local rebuild.",),
)
