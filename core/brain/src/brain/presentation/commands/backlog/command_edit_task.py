# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `edit-task` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="edit-task",
    domain="task backlog",
    help="Edit task fields without changing its state. (e.g. edit-task t1 -t 'Clarify UI')",
    arguments=[
        ArgumentSchema(
            flags=["task_id"], help="Task ID to edit (e.g. t1 or 1).", type="str"
        ),
        ArgumentSchema(
            flags=["--title", "-t"],
            help="Replacement task title.",
            type="str",
            default=None,
        ),
        ArgumentSchema(
            flags=["--description", "-d"],
            help="Replacement task description.",
            type="str",
            default=None,
        ),
        ArgumentSchema(
            flags=["--priority", "-p"],
            help="Replacement priority (HIGH, MEDIUM, LOW).",
            type="str",
            default=None,
        ),
        ArgumentSchema(
            flags=["--domain"],
            help="Replacement dot-notated task domain.",
            type="str",
            default=None,
        ),
    ],
    description="Update selected fields on an existing backlog task.",
    stdin=(),
    examples=("py {LOCAL_BRAIN_SCRIPT} edit-task t1 -t 'Clarify UI'",),
    output=("Updated task details are returned.",),
    exit_codes=("0: task updated", "1: invalid task ID or field value"),
    safeguards=("Only supplied fields are changed; task state is preserved.",),
    notes=("Priority values are HIGH, MEDIUM, or LOW.",),
)
