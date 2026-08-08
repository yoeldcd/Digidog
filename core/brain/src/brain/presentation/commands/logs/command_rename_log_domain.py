"""Command metadata for renaming one log domain subtree."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="rename-log-domain",
    domain="logs",
    help="Rename a log domain and its descendants.",
    arguments=[
        ArgumentSchema(flags=["source"], help="Existing log domain path."),
        ArgumentSchema(flags=["target"], help="Replacement log domain path."),
        ArgumentSchema(flags=["--exact"], action="store_true", help="Rename only direct entries, excluding descendants."),
    ],
)
