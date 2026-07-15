"""Command metadata for the `list-messages` CLI command."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="list-messages",
    domain="general",
    help="List temporary speak jobs and in-memory voice messages.",
    arguments=[ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Render machine-readable JSON.")],
)
