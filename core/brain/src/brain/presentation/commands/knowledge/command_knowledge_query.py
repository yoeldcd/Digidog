# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `knowledge-query` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="knowledge-query",
    domain="knowledge",
    help="Search the knowledge graph with optional hybrid vectorstore results.",
    description="Search graph text and optionally add vectorstore matches, ranked and limited for display.",
    stdin=(
        "No stdin is read; the search text and filters are command-line arguments.",
    ),
    examples=(
        'py {LOCAL_BRAIN_SCRIPT} knowledge-query "climate policy" --limit 5 --scope all --json',
    ),
    output=(
        "Text lists matches with optional rank details. --json emits result records.",
    ),
    exit_codes=(
        "0: query completed, including zero matches.",
        "2: missing/invalid query options or search failure.",
    ),
    safeguards=(
        "This command only reads graph data; --hybrid adds available vectorstore results without changing the graph.",
    ),
    notes=(
        "Limit defaults to 10 and scope defaults to all. Hybrid search is opt-in and may return no vector matches.",
    ),
    arguments=[
        ArgumentSchema(flags=["query"], help="Text to search in the knowledge graph."),
        ArgumentSchema(
            flags=["-l", "--limit"],
            type="int",
            default=10,
            help="Limit number of results.",
        ),
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
        ArgumentSchema(
            flags=["--explain"],
            action="store_true",
            help="Show rank and result kind details.",
        ),
        ArgumentSchema(
            flags=["-j", "--json"], action="store_true", help="Output results as JSON."
        ),
    ],
)
