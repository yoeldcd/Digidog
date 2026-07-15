"""Command metadata for the `update-vectorstore` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="update-vectorstore",
    domain="vectorstore",
    help="Incrementally update modified memory files in the ChromaDB vector store.",
    arguments=[
        ArgumentSchema(flags=["--json"], action="store_true", help="Output results as JSON."),
    ],
)
