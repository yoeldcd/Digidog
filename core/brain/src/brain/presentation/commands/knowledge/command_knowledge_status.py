# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `knowledge-status` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="knowledge-status",
    domain="knowledge",
    help="Display knowledge graph configuration and database statistics.",
    description="Read configuration and entity, relation, class, and delta counts for the selected knowledge scope.",
    stdin=("No stdin is read; scope and output mode are command-line flags.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} knowledge-status --scope all --json",),
    output=(
        "Text prints status and database statistics. --json emits a structured status payload on stdout.",
    ),
    exit_codes=(
        "0: status was read successfully.",
        "2: invalid scope or the database could not be inspected.",
    ),
    safeguards=(
        "This command is read-only; it does not create, update, or delete graph records.",
    ),
    notes=(
        "Scope defaults to all, combining global and local status when both are available.",
    ),
    arguments=[
        ArgumentSchema(
            flags=["--scope"],
            default="all",
            help="Knowledge DB scope: all, global, or local. Defaults to all.",
        ),
        ArgumentSchema(
            flags=["-j", "--json"], action="store_true", help="Output results as JSON."
        ),
    ],
)
