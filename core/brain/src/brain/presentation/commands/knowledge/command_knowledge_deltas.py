# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `knowledge-deltas` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="knowledge-deltas",
    domain="knowledge",
    help="Review pending knowledge graph delta proposals and confirm application.",
    arguments=[
        ArgumentSchema(flags=["--id"], type="int", default=None, help="Review one pending delta by identifier."),
        ArgumentSchema(flags=["-y", "--yes"], action="store_true", help="Apply all applicable reviewed deltas."),
        ArgumentSchema(flags=["-l", "--limit"], type="int", default=10, help="Limit listed pending deltas."),
        ArgumentSchema(flags=["--status"], default="pending", help="Filter by status or use all."),
        ArgumentSchema(
            flags=["--scope"],
            default="global",
            help="Knowledge DB scope: global or local. Defaults to global.",
        ),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Output review/application as JSON."),
    ],
)
