# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for consumer-only avatar message resolution."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="resolve-avatar-message",
    domain="general",
    help="Resolve or acknowledge one opaque avatar message reference as its destination consumer.",
    arguments=[
        ArgumentSchema(flags=["action"], help="Operation: read or ack."),
        ArgumentSchema(flags=["message_id"], help="Opaque avatar message UUID."),
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help="Print machine-readable JSON output.",
        ),
    ],
    description="Read one queued avatar message or acknowledge it for the destination consumer.",
    stdin=("No stdin is consumed.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} resolve-avatar-message read 7f2d... --json",),
    output=("The message envelope for read, or acknowledgement status for ack.",),
    exit_codes=(
        "0 on successful read or acknowledgement; nonzero for unknown message or invalid action.",
    ),
    safeguards=(
        "Only the supplied opaque message UUID is accessed; acknowledgement is explicit.",
    ),
    notes=("Use read before ack when the payload must be inspected.",),
)
