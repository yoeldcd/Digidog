# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for atomic task completion."""

from brain.application.logs.entry_formatting import valid_log_types_text
from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="complete-work",
    domain="general",
    help="Stage explicit files, record a task-derived log, and complete the task.",
    arguments=[
        ArgumentSchema(flags=["task_id"], help="Backlog task id."),
        ArgumentSchema(
            flags=["details"],
            nargs="*",
            help=(
                "Compact form: CHANGE_TYPE SUMMARY. The legacy six-value form "
                "DOMAIN TITLE CHANGE_TYPE WHY DESCRIPTION IMPACT remains accepted. "
                f"Accepted change types: {valid_log_types_text()}."
            ),
        ),
        ArgumentSchema(flags=["--domain"], help="Optional log-domain override; defaults to the task domain."),
        ArgumentSchema(flags=["--title"], help="Optional log-title override; defaults to the task title."),
        ArgumentSchema(flags=["--why"], help="Optional motivation override; defaults to the task description."),
        ArgumentSchema(flags=["--impact"], help="Optional impact override; defaults to the completion summary."),
        ArgumentSchema(flags=["--stage"], required=True, nargs="+", help="Workspace-relative files to stage."),
    ],
)
