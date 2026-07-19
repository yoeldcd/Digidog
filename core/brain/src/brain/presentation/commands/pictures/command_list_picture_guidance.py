"""Command metadata for `list-picture-guidance`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="list-picture-guidance",
    domain="pictures",
    help="List configured img2text tags and known character recognition guidance.",
    arguments=[
        ArgumentSchema(flags=["section"], nargs="?", default="", help="Optional `tags` or `characters` section."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Render machine-readable JSON."),
    ],
)
