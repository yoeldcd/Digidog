"""Command metadata for the `registre-proyect` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="registre-proyect",
    domain="general",
    help="Register a local project workspace path to mirrors list. (Alias of register-project).",
    arguments=[
        ArgumentSchema(flags=["-p", "--path"], type="str", default="", help="Project workspace root path to register. (Defaults to current workspace root)."),
    ],
)
