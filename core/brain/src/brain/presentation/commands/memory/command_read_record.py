"""Command metadata for the `get-memory-entry` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="get-memory-entry",
    domain="memory",
    help="Read Markdown content from a memory domain key. (e.g. get-memory-entry profile.friend yoi)",
    arguments=[
        ArgumentSchema(flags=["domain"], help="The memory domain or dot-separated subdomain (e.g. domain or domain.subdomain)."),
        ArgumentSchema(flags=["key"], default=None, nargs="?", help="The name of the key to read (optional if domain.key notation is used)."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Output content inside a JSON wrapper."),
        ArgumentSchema(flags=["-ft", "--full-text"], action="store_true", help="Print the entire content of all files in the domain instead of a navigable tree."),
        ArgumentSchema(flags=["-uo", "--uptime-order"], action="store_true", help="Sort the tree by modification date (newest first)."),
        ArgumentSchema(flags=["-l", "--limit"], type="int", default=None, help="Limit the number of tree items per level or lines printed."),
    ],
)
