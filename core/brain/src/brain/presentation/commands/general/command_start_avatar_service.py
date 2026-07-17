# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for `start-avatar-service`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="start-avatar-service",
    domain="general",
    help="Idempotently start the detached avatar service.",
    arguments=[
        ArgumentSchema(
            flags=["--mode"],
            default="light",
            help="Avatar presentation theme: dark or light.",
        ),
    ],
)
