"""Command metadata for `describe-picture`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="describe-picture",
    domain="pictures",
    help="Set a manual description or invoke the configured img2text model.",
    arguments=[
        ArgumentSchema(flags=["picture_id"], help="Registered picture identifier."),
        ArgumentSchema(flags=["description"], nargs="?", default="", help="Manual description; omit for img2text."),
        ArgumentSchema(flags=["--prompt"], default="", help="Optional img2text prompt override."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Render machine-readable JSON."),
    ],
)
