# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `task-finished` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="task-finished",
    domain="task backlog",
    help="Mark a workspace task as finished. (e.g. task-finished t1)",
    arguments=[
        ArgumentSchema(
            flags=["task_id"],
            help="Task ID to finish (e.g. t1 or 1).",
            type="str",
        ),
    ],
    description="Mark a backlog task as finished.",
    stdin=(),
    examples=("py {LOCAL_BRAIN_SCRIPT} task-finished t1",),
    output=("The finished task record is returned.",),
    exit_codes=("0: task marked DONE", "1: task ID not found"),
    safeguards=("The task must exist before its status is changed.",),
    notes=("This is equivalent to setting the task status to DONE.",),
)
