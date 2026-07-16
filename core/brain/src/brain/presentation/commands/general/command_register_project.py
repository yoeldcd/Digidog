# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `register-project` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="register-project",
    domain="general",
    help="Register a local project workspace path to mirrors list.",
    arguments=[
        ArgumentSchema(flags=["-p", "--path"], type="str", default="", help="Project workspace root path to register. (Defaults to current workspace root)."),
    ],
)
