# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `knowledge-export` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="knowledge-export",
    domain="knowledge",
    help="Export the knowledge graph as JSON-LD.",
    description="Serialize the selected knowledge graph as JSON-LD on stdout.",
    stdin=("No stdin is read; format, scope, and output mode are command-line flags.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} knowledge-export --scope all --json",),
    output=(
        "The JSON-LD document is written to stdout; --json keeps the command envelope machine-readable.",
    ),
    exit_codes=(
        "0: export completed.",
        "2: unsupported format, invalid scope, or export failure.",
    ),
    safeguards=(
        "Export is read-only and does not mutate graph data or pending deltas.",
    ),
    notes=(
        "Only jsonld is supported. Scope defaults to all and includes global and local graph data when available.",
    ),
    arguments=[
        ArgumentSchema(
            flags=["--format"],
            default="jsonld",
            help="Export format. Currently only jsonld is supported.",
        ),
        ArgumentSchema(
            flags=["--scope"],
            default="all",
            help="Knowledge DB scope: all, global, or local. Defaults to all.",
        ),
        ArgumentSchema(
            flags=["--json"], action="store_true", help="Keep output machine-readable."
        ),
    ],
)
