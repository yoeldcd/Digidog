# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `get-context` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="get-context",
    domain="general",
    help="Hydrate LLM context with memory indexes, available profiles, and recent diary summaries.",
    arguments=[
        ArgumentSchema(flags=["-ld", "--limit-diary"], type="int", default=3, help="Number of recent diary files to include."),
        ArgumentSchema(flags=["--domain"], type="str", default="", help="Highlight or filter logs matching the specified domain."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Print machine-readable context cards."),
    ],
)
