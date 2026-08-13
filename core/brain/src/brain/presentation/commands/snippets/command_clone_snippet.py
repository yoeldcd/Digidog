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
        ArgumentSchema(
            flags=["-d", "--dest"],
            required=False,
            help="Target destination directory (relative to workspace root). Defaults to '$agent/scripts'.",
        ),
    ],
    description="Copy a named reusable snippet into the requested workspace destination.",
    stdin=(),
    examples=(
        "py {LOCAL_BRAIN_SCRIPT} clone-snippet utility_name --dest ./$agent/scripts",
    ),
    output=("Destination path and copied files.",),
    exit_codes=(
        "0: snippet cloned.",
        "1: snippet missing or destination write failed.",
    ),
    safeguards=(
        "Source snippets are read-only; destination remains within the selected workspace.",
    ),
    notes=("When --dest is omitted, the configured scripts directory is used.",),
)
