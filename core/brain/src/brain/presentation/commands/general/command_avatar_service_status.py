# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for `avatar-service-status`."""
from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="avatar-service-status",
    domain="general",
    help="Show avatar service state, retained messages, and presentation errors.",
    arguments=[ArgumentSchema(flags=["--color"], action="store_true", help="Use ANSI colors for human-readable output.")],
)
