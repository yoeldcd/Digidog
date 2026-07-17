# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `query` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="query",
    domain="general",
    help="Search the brain through one global query point across knowledge graph and memory.",
    arguments=[
        ArgumentSchema(
            flags=["domain"],
            nargs="?",
            help="Optional memory domain filter. If omitted, the first positional value is treated as the query.",
        ),
        ArgumentSchema(flags=["query"], nargs="?", help="Text to search globally."),
        ArgumentSchema(flags=["-l", "--limit"], type="int", default=5, help="Limit matches per selected backend."),
        ArgumentSchema(
            flags=["--source"],
            default="all",
            help="Query source: all, memory, knowledge, messages, or pictures. Defaults to all.",
        ),
        ArgumentSchema(
            flags=["--messages"],
            action="store_true",
            help="Search only persisted avatar messages. Equivalent to --source messages.",
        ),
        ArgumentSchema(
            flags=["--scope"],
            default=None,
            help="Backward-compatible alias for --source.",
        ),
        ArgumentSchema(
            flags=["--mechanism"],
            default="all",
            help="Query mechanism: all, graph, vector, or text. Defaults to all.",
        ),
        ArgumentSchema(
            flags=["--knowledge-scope"],
            default="all",
            help="Knowledge DB scope: all, global, or local. Defaults to all.",
        ),
        ArgumentSchema(
            flags=["--deep"],
            action="store_true",
            help="Run deep retrieval: parse context, run subqueries, rank evidence, and synthesize an answer.",
        ),
        ArgumentSchema(flags=["--explain"], action="store_true", help="Show source, kind, and rank details."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Output results as JSON."),
    ],
)
