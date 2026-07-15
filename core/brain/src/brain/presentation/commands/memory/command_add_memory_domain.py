"""Command metadata for the `add-memory-domain` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="add-memory-domain",
    domain="memory",
    help="Create a memory domain or subdomain (e.g. domain or domain.subdomain). (e.g. add-memory-domain profile.friend)",
    arguments=[
        ArgumentSchema(
            flags=["domain"],
            help="Name of the memory domain or dot-separated subdomain.",
        ),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Output result as JSON."),
    ],
)
