"""Command metadata for the `update-memory-index` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="update-memory-index",
    domain="memory",
    help="Refresh the memory source registry.",
    description="Rebuild the memory source registry from current Markdown files and filesystem timestamps.",
    stdin=("No stdin is read; only the optional --json flag is accepted.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} update-memory-index --json",),
    output=(
        "Text mode prints a refresh message; --json prints {ok:true,message} or {ok:false,error}.",
    ),
    exit_codes=("0: registry refreshed.", "1: filesystem or registry refresh failed."),
    safeguards=(
        "The action ensures the memory root exists, then scans only .md files under that root.",
    ),
    notes=(
        "Refreshing updates registry metadata; it does not rewrite Markdown entry contents.",
    ),
    arguments=[
        ArgumentSchema(
            flags=["--json"], action="store_true", help="Output result as JSON."
        ),
    ],
)
