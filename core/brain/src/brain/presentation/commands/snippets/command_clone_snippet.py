# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `clone-snippet` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="clone-snippet",
    domain="snippets",
    help="Copy a reusable snippet from the configured agent directory to the workspace.",
    arguments=[
        ArgumentSchema(flags=["name"], help="The name of the snippet to clone."),
        ArgumentSchema(flags=["-d", "--dest"], required=False, help="Target destination directory (relative to workspace root). Defaults to '$agent/scripts'."),
    ],
)
