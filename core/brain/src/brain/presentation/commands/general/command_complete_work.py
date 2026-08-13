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
                f"Accepted values: {valid_log_types_text()}."
            ),
        ),
        ArgumentSchema(
            flags=["--domain"],
            help="Optional log-domain override; defaults to the task domain.",
        ),
        ArgumentSchema(
            flags=["--title"],
            help="Optional log-title override; defaults to the task title.",
        ),
        ArgumentSchema(
            flags=["--why"],
            help="Optional motivation override; defaults to the task description.",
        ),
        ArgumentSchema(
            flags=["--impact"],
            help="Optional impact override; defaults to the completion summary.",
        ),
        ArgumentSchema(
            flags=["--stage"],
            required=True,
            nargs="+",
            help="Workspace-relative files to stage.",
        ),
    ],
    description="Stage explicit files, append the completion log, and mark a backlog task complete.",
    stdin=("No stdin is consumed; task and files are supplied as arguments.",),
    examples=(
        "py {LOCAL_BRAIN_SCRIPT} complete-work t123 fix 'Repair parser' --stage src/app.py",
    ),
    output=("Completion summary with staged paths and recorded log identifier.",),
    exit_codes=(
        "0 when staging, logging, and completion succeed; nonzero on validation failure.",
    ),
    safeguards=(
        "Only explicitly listed workspace-relative paths are staged; task metadata supplies defaults.",
    ),
    notes=("This command mutates git staging and the task/log stores.",),
)
