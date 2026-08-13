# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `registre-proyect` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="registre-proyect",
    domain="general",
    help="Register a local project workspace path to mirrors list. (Alias of register-project).",
    arguments=[
        ArgumentSchema(
            flags=["-p", "--path"],
            type="str",
            default="",
            help="Project workspace root path to register. (Defaults to current workspace root).",
        ),
    ],
    description="Compatibility alias that registers a workspace root in the project mirrors list.",
    stdin=("No stdin is consumed.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} registre-proyect --path D:\\work\\project",),
    output=("Registered project path and resulting mirror metadata.",),
    exit_codes=(
        "0 when registration succeeds; nonzero when validation or persistence fails.",
    ),
    safeguards=("The alias preserves register-project validation and normalization.",),
    notes=(
        "Prefer register-project in new scripts; this name remains supported for compatibility.",
    ),
)
