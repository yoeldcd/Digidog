# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `init` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="init",
    aliases=["wakeup"],
    domain="general",
    help="Initialize session: run checks and output LLM context hydration payload.",
    arguments=[
        ArgumentSchema(
            flags=["-ld", "--limit-diary"],
            type="int",
            default=3,
            help="Number of recent diary files to include.",
        ),
        ArgumentSchema(
            flags=["--domain"],
            type="str",
            default="",
            help="Highlight or filter logs matching the specified domain.",
        ),
    ],
    description="Initialize a session by checking the workspace and emitting context hydration data.",
    stdin=("No stdin is consumed.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} init --limit-diary 5",),
    output=("Initialization checks followed by context payload output.",),
    exit_codes=(
        "0 when checks and hydration complete; nonzero on initialization failure.",
    ),
    safeguards=("Initialization is read-only and does not alter memory records.",),
    notes=("The wakeup alias invokes the same command.",),
)
