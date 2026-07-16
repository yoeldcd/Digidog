# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `knowledge-export` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="knowledge-export",
    domain="knowledge",
    help="Export the knowledge graph as JSON-LD.",
    arguments=[
        ArgumentSchema(flags=["--format"], default="jsonld", help="Export format. Currently only jsonld is supported."),
        ArgumentSchema(
            flags=["--scope"],
            default="all",
            help="Knowledge DB scope: all, global, or local. Defaults to all.",
        ),
        ArgumentSchema(flags=["--json"], action="store_true", help="Keep output machine-readable."),
    ],
)
