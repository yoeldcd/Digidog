# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `knowledge-deltas` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="knowledge-deltas",
    domain="knowledge",
    help="Review pending knowledge graph delta proposals and confirm application.",
    description="List pending knowledge delta proposals and optionally apply the reviewed set.",
    stdin=(
        "No stdin is read; review filters, scope, confirmation, and output mode are flags.",
    ),
    examples=("py {LOCAL_BRAIN_SCRIPT} knowledge-deltas --scope local --json",),
    output=(
        "Text lists matching proposals and reports applied counts. --json emits proposal and application details.",
    ),
    exit_codes=(
        "0: listing completed or confirmed applications finished.",
        "2: invalid filters or application failure.",
    ),
    safeguards=(
        "Without --yes, applying proposals requires confirmation; omitting --yes leaves deltas pending.",
    ),
    notes=(
        "Status defaults to pending, limit to 10, and scope to global. --id narrows review to one proposal.",
    ),
    arguments=[
        ArgumentSchema(
            flags=["--id"],
            type="int",
            default=None,
            help="Review one pending delta by identifier.",
        ),
        ArgumentSchema(
            flags=["-y", "--yes"],
            action="store_true",
            help="Apply all applicable reviewed deltas.",
        ),
        ArgumentSchema(
            flags=["-l", "--limit"],
            type="int",
            default=10,
            help="Limit listed pending deltas.",
        ),
        ArgumentSchema(
            flags=["--status"], default="pending", help="Filter by status or use all."
        ),
        ArgumentSchema(
            flags=["--scope"],
            default="global",
            help="Knowledge DB scope: global or local. Defaults to global.",
        ),
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help="Output review/application as JSON.",
        ),
    ],
)
