# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `rebuild-local-vectorstore` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="rebuild-local-vectorstore",
    domain="vectorstore",
    help="Reset and rebuild a local vector collection from scratch. (Destructive command, use update-local-vectorstore for incremental updates).",
    arguments=[
        ArgumentSchema(
            flags=["-y", "--yes"],
            action="store_true",
            help="Skip confirmation prompt for destructive rebuild.",
        ),
        ArgumentSchema(
            flags=["--collection"],
            default="logs",
            help="The name of the local collection to rebuild (default: logs).",
        ),
        ArgumentSchema(
            flags=["-j", "--json"], action="store_true", help="Output result as JSON."
        ),
    ],
    description="Delete and rebuild one local vector collection from current memory files.",
    stdin=(),
    examples=(
        "py {LOCAL_BRAIN_SCRIPT} rebuild-local-vectorstore --collection logs --yes",
    ),
    output=("Rebuild counts and collection status.",),
    exit_codes=(
        "0: collection rebuilt.",
        "1: confirmation, indexing, or storage failure.",
    ),
    safeguards=("Requires --yes to bypass the destructive confirmation prompt.",),
    notes=("Use update-local-vectorstore for incremental changes.",),
)
