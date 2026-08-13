# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `list-snippets` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="list-snippets",
    aliases=["list-utilities"],
    domain="snippets",
    help="Search or list reusable utilities from agent snippets and consumer scripts.",
    arguments=[
        ArgumentSchema(
            flags=["--scope"],
            default="all",
            help="Utility scope: local, global, or all. Defaults to all.",
        ),
        ArgumentSchema(
            flags=["-f", "--filter"], help="Optional filter to search in utility names."
        ),
        ArgumentSchema(
            flags=["query"],
            nargs="?",
            help="Optional keyword to search in snippet names.",
        ),
    ],
    description="List reusable snippets, optionally filtering by scope, name, or query.",
    stdin=(),
    examples=("py {LOCAL_BRAIN_SCRIPT} list-snippets --scope local",),
    output=("Matching snippet names and locations.",),
    exit_codes=("0: snippets listed.", "1: snippet index could not be read."),
    safeguards=("Read-only search; no snippet files are modified.",),
    notes=("Scope accepts local, global, or all.",),
)
