"""Command metadata for the `local-vectorstore-status` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="local-vectorstore-status",
    domain="vectorstore",
    help="Display ChromaDB configuration, collections, and vector statistics for the local workspace store.",
    arguments=[
        ArgumentSchema(flags=["--json"], action="store_true", help="Output results as JSON."),
    ],
)
