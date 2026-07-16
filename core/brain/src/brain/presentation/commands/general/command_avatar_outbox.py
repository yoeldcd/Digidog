# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for native avatar outbox bridge operations."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="avatar-outbox",
    domain="general",
    help="Inspect, claim, acknowledge, or release messages queued for native Codex delivery.",
    arguments=[
        ArgumentSchema(flags=["action"], help="Operation: list, claim, ack, or release."),
        ArgumentSchema(flags=["message_id"], nargs="?", default="", help="Message UUID required by ack/release."),
        ArgumentSchema(flags=["--limit"], type="int", default=20, help="Maximum messages returned by list/claim."),
        ArgumentSchema(flags=["--lease-seconds"], type="int", default=600, help="Claim lease duration (60-3600)."),
        ArgumentSchema(flags=["--claim-token"], default="", help="Lease token required by ack/release."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Print machine-readable JSON output."),
    ],
)
