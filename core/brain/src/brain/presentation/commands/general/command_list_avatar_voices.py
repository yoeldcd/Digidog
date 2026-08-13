# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for `list-avatar-voices`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="list-avatar-voices",
    domain="general",
    help="List voices and voice models exposed by an avatar speech engine.",
    arguments=[
        ArgumentSchema(
            flags=["--engine"],
            default="",
            nargs="?",
            help="Engine name. An empty or omitted value resolves the active engine.",
        ),
    ],
    description="List voices exposed by the selected or active avatar speech engine.",
    stdin=("No stdin is consumed.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} list-avatar-voices --engine edge",),
    output=("Available voice names and engine metadata.",),
    exit_codes=("0 when the engine responds; nonzero when it is unavailable.",),
    safeguards=("Read-only engine discovery; no voice settings are changed.",),
    notes=("Omitting --engine uses the active configured engine.",),
)
