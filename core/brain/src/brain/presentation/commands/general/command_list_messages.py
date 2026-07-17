# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `list-messages` CLI command."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="list-messages",
    domain="general",
    help="List persisted avatar messages for the local consumer.",
    arguments=[
        ArgumentSchema(flags=["--query"], default="", help="Filter message text by literal substring."),
        ArgumentSchema(flags=["--chat-id"], default="", help="Filter by Codex chat identifier."),
        ArgumentSchema(flags=["--emotion"], default="", help="Filter by exact emotion."),
        ArgumentSchema(flags=["--source-command"], default="", help="Filter narrated operations by command."),
        ArgumentSchema(flags=["--limit"], type=int, default=100, help="Maximum records, from 1 to 500."),
        ArgumentSchema(flags=["--offset"], type=int, default=0, help="Non-negative pagination offset."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Render machine-readable JSON."),
    ],
)
