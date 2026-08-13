# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `delete-knowledge-deltas` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="delete-knowledge-deltas",
    domain="knowledge",
    help="Delete unwanted pending knowledge graph delta proposals.",
    description=(
        "Delete selected pending knowledge delta proposals, legacy deltas, or all candidates matching the filters."
    ),
    stdin=(
        "No stdin is read; IDs, filters, scope, confirmation, and output mode are command-line flags.",
    ),
    examples=("py {LOCAL_BRAIN_SCRIPT} delete-knowledge-deltas --scope local --json",),
    output=(
        "Text reports candidates and deletion counts. --json emits the deletion summary as structured data.",
    ),
    exit_codes=(
        "0: deletion completed or no candidates matched.",
        "2: invalid filters or deletion failure.",
    ),
    safeguards=(
        "Deletion requires confirmation unless --yes is set; --all and --legacy broaden the destructive selection.",
    ),
    notes=(
        "Scope defaults to global; inspection is capped at 200 and IDs, status, and limit constrain selection.",
    ),
    arguments=[
        ArgumentSchema(
            flags=["ids"], type="int", nargs="*", help="Pending delta IDs to delete."
        ),
        ArgumentSchema(
            flags=["--all"],
            action="store_true",
            help="Delete all deltas inspected by the limit.",
        ),
        ArgumentSchema(
            flags=["--legacy"],
            action="store_true",
            help="Delete legacy deltas from retired contracts.",
        ),
        ArgumentSchema(
            flags=["--status"], default=None, help="Delete deltas matching a status."
        ),
        ArgumentSchema(
            flags=["--scope"],
            default="global",
            help="Knowledge DB scope: global or local. Defaults to global.",
        ),
        ArgumentSchema(
            flags=["--limit"],
            type="int",
            default=200,
            help="Maximum candidate deltas to inspect.",
        ),
        ArgumentSchema(
            flags=["-y", "--yes"],
            action="store_true",
            help="Skip deletion confirmation.",
        ),
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help="Output deletion summary as JSON.",
        ),
    ],
)
