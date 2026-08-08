"""Command metadata for renaming one backlog domain subtree."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="rename-task-domain",
    domain="task backlog",
    help="Rename a backlog domain and its descendants.",
    arguments=[
        ArgumentSchema(flags=["source"], help="Existing backlog domain path."),
        ArgumentSchema(flags=["target"], help="Replacement backlog domain path."),
        ArgumentSchema(flags=["--exact"], action="store_true", help="Rename only direct tasks, excluding descendants."),
    ],
)
