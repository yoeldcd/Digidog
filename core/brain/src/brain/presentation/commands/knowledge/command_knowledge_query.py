"""Command metadata for the `knowledge-query` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="knowledge-query",
    domain="knowledge",
    help="Search the knowledge graph with optional hybrid vectorstore results.",
    arguments=[
        ArgumentSchema(flags=["query"], help="Text to search in the knowledge graph."),
        ArgumentSchema(flags=["-l", "--limit"], type="int", default=10, help="Limit number of results."),
        ArgumentSchema(
            flags=["--hybrid"],
            action="store_true",
            help="Include vectorstore memory matches when available.",
        ),
        ArgumentSchema(
            flags=["--scope"],
            default="all",
            help="Knowledge DB scope: all, global, or local. Defaults to all.",
        ),
        ArgumentSchema(flags=["--explain"], action="store_true", help="Show rank and result kind details."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Output results as JSON."),
    ],
)
