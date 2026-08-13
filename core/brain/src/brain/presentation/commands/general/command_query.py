from __future__ import annotations

# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `query` CLI command."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="query",
    domain="general",
    help="Search the brain through one global query point across knowledge graph, memory, messages, and pictures with broad keyword fallback.",
    arguments=[
        ArgumentSchema(
            flags=["domain"],
            nargs="?",
            help="Optional memory domain filter. If omitted, the first positional value is treated as the query.",
        ),
        ArgumentSchema(flags=["query"], nargs="?", help="Text to search globally."),
        ArgumentSchema(
            flags=["-l", "--limit"],
            type="int",
            default=5,
            help="Limit matches per selected backend.",
        ),
        ArgumentSchema(
            flags=["--page"],
            type="int",
            default=1,
            help="1-based result page for shallow queries.",
        ),
        ArgumentSchema(
            flags=["--page-size"],
            type="int",
            default=25,
            help="Results per page for shallow queries: 0 (all), 10, 25, 50, or 100.",
        ),
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
            help="Alias for --knowledge-scope: all, global, or local.",
        ),
        ArgumentSchema(
            flags=["--mechanism"],
            default="all",
            help="Query mechanism: all, graph, vector, or text (with broad keyword fallback). Defaults to all.",
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
        ArgumentSchema(
            flags=["--explain"],
            action="store_true",
            help="Show source, kind, and rank details.",
        ),
        ArgumentSchema(
            flags=["-j", "--json"], action="store_true", help="Output results as JSON."
        ),
        ArgumentSchema(
            flags=["--verbose-schema"],
            action="store_true",
            help="Output the full internal query DTO schema.",
        ),
    ],
    description="Search configured Brain sources and optionally return ranked deep retrieval context.",
    stdin=("No stdin is consumed; provide query text as arguments.",),
    examples=('py {LOCAL_BRAIN_SCRIPT} query "architecture" --json',),
    output=("Matching records or synthesized deep context; JSON when --json is set.",),
    exit_codes=(
        "0 on successful retrieval; nonzero when arguments or backend access fail.",
    ),
    safeguards=(
        "Validates source, mechanism, scope, and pagination values before querying.",
    ),
    notes=("Without --deep, results are paginated shallow matches.",),
)
