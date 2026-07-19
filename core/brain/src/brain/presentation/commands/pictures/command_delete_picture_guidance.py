"""Command metadata for `delete-picture-guidance`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="delete-picture-guidance",
    domain="pictures",
    help="Delete one configured img2text tag or known character description.",
    arguments=[
        ArgumentSchema(flags=["section"], help="Target `tags` or `characters` section."),
        ArgumentSchema(flags=["name"], help="Existing tag label or known character name."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Render machine-readable JSON."),
    ],
)
