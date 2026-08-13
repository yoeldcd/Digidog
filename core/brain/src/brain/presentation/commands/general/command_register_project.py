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
        ArgumentSchema(
            flags=["-p", "--path"],
            type="str",
            default="",
            help="Project workspace root path to register. (Defaults to current workspace root).",
        ),
    ],
    description="Register a workspace root in the local project mirrors list.",
    stdin=("No stdin is consumed.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} register-project --path D:\\work\\project",),
    output=("Registered project path and resulting mirror metadata.",),
    exit_codes=(
        "0 when registration succeeds; nonzero when the path is invalid or cannot be persisted.",
    ),
    safeguards=("The path is normalized and validated before persistence.",),
    notes=("Omitting --path uses the current workspace root.",),
)
