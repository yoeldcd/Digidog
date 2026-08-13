"""Command metadata for the `memory-structure` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="memory-structure",
    domain="memory",
    help="List memory domains, subdomains, and registered entries in a tree structure. (e.g. memory-structure --limit 5)",
    description="Render indexed memory domains and entries as paths or a terminal tree.",
    stdin=("No stdin is read; ordering, limit, and format are flags.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} memory-structure --json",),
    output=(
        "Text mode draws the hierarchy with entry metadata; --json prints a list of dotted paths.",
    ),
    exit_codes=(
        "0: structure rendered, including an empty-store notice.",
        "1: invalid limit or index loading failed.",
    ),
    safeguards=(
        "The command only loads the index; negative --limit values are rejected before rendering.",
    ),
    notes=(
        "--uptime-order sorts each level by newest modification time; --limit applies per level.",
    ),
    arguments=[
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help="Print machine-readable JSON list of paths.",
        ),
        ArgumentSchema(
            flags=["-uo", "--uptime-order"],
            action="store_true",
            help="Sort the tree by modification date (newest first).",
        ),
        ArgumentSchema(
            flags=["-l", "--limit"],
            type="int",
            default=None,
            help="Limit the number of tree items per level.",
        ),
    ],
)
