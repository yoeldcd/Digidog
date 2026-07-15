"""Command metadata for `list-avatar-voices`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="list-avatar-voices",
    domain="general",
    help="List voices and voice models exposed by an avatar speech engine.",
    arguments=[
        ArgumentSchema(
            flags=["--engine"],
            default="",
            nargs="?",
            help="Engine name. An empty or omitted value resolves the active engine.",
        ),
    ],
)
