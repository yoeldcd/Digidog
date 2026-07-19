"""Command metadata for `set-picture-guidance`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="set-picture-guidance",
    domain="pictures",
    help="Create or update one img2text tag or known character description.",
    arguments=[
        ArgumentSchema(flags=["section"], help="Target `tags` or `characters` section."),
        ArgumentSchema(flags=["name"], help="Tag label or known character name."),
        ArgumentSchema(flags=["description"], help="Observable identification criteria."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Render machine-readable JSON."),
    ],
)
