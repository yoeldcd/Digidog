"""Command metadata for the `set-memory-entry` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="set-memory-entry",
    domain="memory",
    help="Write content to a key inside a memory domain. (e.g. set-memory-entry profile.friend yoi 'presence info')",
    arguments=[
        ArgumentSchema(flags=["domain"], help="The memory domain or dot-separated subdomain (e.g. domain or domain.subdomain)."),
        ArgumentSchema(flags=["key"], default=None, nargs="?", help="The name of the key to create/update (optional if domain.key notation is used)."),
        ArgumentSchema(flags=["val"], default=None, nargs="?", help="The Markdown content to write. If omitted, reads from stdin."),
        ArgumentSchema(flags=["-v", "--value"], required=False, help="Alternative option to provide Markdown content."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Output result as JSON."),
    ],
)
