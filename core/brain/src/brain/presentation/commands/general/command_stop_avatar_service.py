"""Command metadata for `stop-avatar-service`."""

from brain.presentation.commands.models import CommandSchema


SCHEMA = CommandSchema(
    name="stop-avatar-service",
    domain="general",
    help="Gracefully stop the avatar service.",
    arguments=[],
)
