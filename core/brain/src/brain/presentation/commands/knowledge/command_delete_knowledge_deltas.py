# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `delete-knowledge-deltas` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="delete-knowledge-deltas",
    domain="knowledge",
    help="Delete unwanted pending knowledge graph delta proposals.",
    arguments=[
        ArgumentSchema(flags=["ids"], type="int", nargs="*", help="Pending delta IDs to delete."),
        ArgumentSchema(flags=["--all"], action="store_true", help="Delete all deltas inspected by the limit."),
        ArgumentSchema(flags=["--legacy"], action="store_true", help="Delete legacy deltas from retired contracts."),
        ArgumentSchema(flags=["--status"], default=None, help="Delete deltas matching a status."),
        ArgumentSchema(
            flags=["--scope"],
            default="global",
            help="Knowledge DB scope: global or local. Defaults to global.",
        ),
        ArgumentSchema(flags=["--limit"], type="int", default=200, help="Maximum candidate deltas to inspect."),
        ArgumentSchema(flags=["-y", "--yes"], action="store_true", help="Skip deletion confirmation."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Output deletion summary as JSON."),
    ],
)
