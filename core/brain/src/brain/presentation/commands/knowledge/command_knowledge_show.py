# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `knowledge-show` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="knowledge-show",
    domain="knowledge",
    help="Show knowledge graph entities, relations, classes, or one entity.",
    arguments=[
        ArgumentSchema(
            flags=["entity"],
            nargs="?",
            default=None,
            help="Entity ID, canonical name, alias, or listing filter.",
        ),
        ArgumentSchema(flags=["--entities"], action="store_true", help="List knowledge graph entities."),
        ArgumentSchema(flags=["--relations"], action="store_true", help="List knowledge graph relations."),
        ArgumentSchema(flags=["--classes"], action="store_true", help="List registered entity classes."),
        ArgumentSchema(flags=["--filter"], default=None, help="Filter listed rows by text."),
        ArgumentSchema(
            flags=["--scope"],
            default="global",
            help="Knowledge DB scope: global or local. Defaults to global.",
        ),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Output results as JSON."),
    ],
)
