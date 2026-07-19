"""Command metadata for `scan-images`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="scan-images",
    aliases=["scan-pictures"],
    domain="pictures",
    help="Synchronize the agent picture tree into canonical SQLite storage.",
    arguments=[
        ArgumentSchema(flags=["--index"], action="store_true", help="Also update reference-only picture vectors."),
        ArgumentSchema(
            flags=["--describe"],
            action="store_true",
            help="After scanning, generate descriptions only for active records whose description is empty.",
        ),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Render machine-readable JSON."),
    ],
)
