"""Command metadata for the `delete-memory-entry` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="delete-memory-entry",
    domain="memory",
    help="Delete a specific key or an entire memory domain. (e.g. delete-memory-entry profile.friend yoi)",
    arguments=[
        ArgumentSchema(flags=["domain"], help="The memory domain or subdomain name (e.g. domain)."),
        ArgumentSchema(flags=["key"], default=None, required=False, nargs="?", help="The key to delete. If omitted, deletes the entire memory domain."),
        ArgumentSchema(flags=["-co", "--confirm"], default="", help="Must match the memory domain name to confirm recursive deletion."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Output result as JSON."),
    ],
)
