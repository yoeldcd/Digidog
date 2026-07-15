"""Command metadata for `start-avatar-service`."""

from brain.presentation.commands.models import CommandSchema


SCHEMA = CommandSchema(
    name="start-avatar-service",
    domain="general",
    help="Idempotently start the elevated avatar service.",
    arguments=[],
)
