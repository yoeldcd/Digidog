"""Command metadata for `describe-image`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="describe-image",
    aliases=["describe-picture"],
    domain="pictures",
    help="Describe one or many registered images with manual text or img2text.",
    arguments=[
        ArgumentSchema(flags=["picture_id"], nargs="?", default="", help="Registered picture identifier."),
        ArgumentSchema(flags=["description"], nargs="?", default="", help="Manual description; omit for img2text."),
        ArgumentSchema(flags=["--all"], action="store_true", help="Regenerate model descriptions for all active images."),
        ArgumentSchema(
            flags=["--undescribeds", "--undescribed"],
            action="store_true",
            help="Describe only active images whose description is empty.",
        ),
        ArgumentSchema(flags=["--prompt"], default="", help="Optional img2text prompt override."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Render machine-readable JSON."),
    ],
)
