"""Command metadata for the `rebuild-local-vectorstore` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="rebuild-local-vectorstore",
    domain="vectorstore",
    help="Reset and rebuild a local vector collection from scratch. (Destructive command, use update-local-vectorstore for incremental updates).",
    arguments=[
        ArgumentSchema(flags=["-y", "--yes"], action="store_true", help="Skip confirmation prompt for destructive rebuild."),
        ArgumentSchema(flags=["--collection"], default="logs", help="The name of the local collection to rebuild (default: logs)."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Output result as JSON."),
    ],
)
