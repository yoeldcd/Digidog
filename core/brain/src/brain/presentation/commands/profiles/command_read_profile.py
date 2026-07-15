"""Command metadata for the `read-profile` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="read-profile",
    domain="profiles",
    help="Read every Markdown entry for one agent profile in a single call.",
    arguments=[
        ArgumentSchema(flags=["name"], help="Profile name to read, for example developer, friend, or research."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Print machine-readable profile entries."),
    ],
)
