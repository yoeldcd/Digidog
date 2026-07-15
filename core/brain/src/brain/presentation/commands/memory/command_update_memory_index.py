"""Command metadata for the `update-memory-index` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="update-memory-index",
    domain="memory",
    help="Refresh the memory source registry.",
    arguments=[
        ArgumentSchema(flags=["--json"], action="store_true", help="Output result as JSON."),
    ],
)
