# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `vectorstore-status` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="vectorstore-status",
    domain="vectorstore",
    help="Display ChromaDB configuration, active models, and memory vector statistics.",
    arguments=[
        ArgumentSchema(flags=["--json"], action="store_true", help="Output results as JSON."),
    ],
)
