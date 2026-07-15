"""Command metadata for consumer-only avatar message resolution."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="resolve-avatar-message",
    domain="general",
    help="Resolve or acknowledge one opaque avatar message reference as its destination consumer.",
    arguments=[
        ArgumentSchema(flags=["action"], help="Operation: read or ack."),
        ArgumentSchema(flags=["message_id"], help="Opaque avatar message UUID."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Print machine-readable JSON output."),
    ],
)
