"""Command metadata for the `init` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="init",
    aliases=["wakeup"],
    domain="general",
    help="Initialize session: run checks and output LLM context hydration payload.",
    arguments=[
        ArgumentSchema(flags=["-ld", "--limit-diary"], type="int", default=3, help="Number of recent diary files to include."),
        ArgumentSchema(flags=["--domain"], type="str", default="", help="Highlight or filter logs matching the specified domain."),
    ],
)
