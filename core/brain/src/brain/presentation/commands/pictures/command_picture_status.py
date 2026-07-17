"""Command metadata for `picture-status`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="picture-status",
    domain="pictures",
    help="Report picture registry, domains, descriptions, and img2text configuration.",
    arguments=[ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Render machine-readable JSON.")],
)
