"""Command metadata for the `memory-structure` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="memory-structure",
    domain="memory",
    help="List memory domains, subdomains, and registered entries in a tree structure. (e.g. memory-structure --limit 5)",
    arguments=[
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Print machine-readable JSON list of paths."),
        ArgumentSchema(flags=["-uo", "--uptime-order"], action="store_true", help="Sort the tree by modification date (newest first)."),
        ArgumentSchema(flags=["-l", "--limit"], type="int", default=None, help="Limit the number of tree items per level."),
    ],
)
