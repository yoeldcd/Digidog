# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for atomic task completion."""

from brain.application.logs.entry_formatting import valid_log_types_text
from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="complete-work",
    domain="general",
    help="Stage explicit files, append a log, refresh its index, and complete a task.",
    arguments=[
        ArgumentSchema(flags=["task_id"], help="Backlog task id."),
        ArgumentSchema(flags=["domain"], help="Changed log domain."),
        ArgumentSchema(flags=["title"], help="Log title."),
        ArgumentSchema(flags=["change_type"], help=f"Log change type. Accepted values: {valid_log_types_text()}."),
        ArgumentSchema(flags=["why"], help="Reason for the change."),
        ArgumentSchema(flags=["description"], help="Implemented change."),
        ArgumentSchema(flags=["impact"], help="Resulting impact."),
        ArgumentSchema(flags=["--stage"], required=True, nargs="+", help="Workspace-relative files to stage."),
    ],
)
