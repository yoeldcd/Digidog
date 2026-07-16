# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `set-task-status` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="set-task-status",
    domain="task backlog",
    help="Set a task state to WORKING or DONE. (e.g. set-task-status t1 DONE)",
    arguments=[
        ArgumentSchema(flags=["task_id"], help="Task ID to update (e.g. t1 or 1).", type="str"),
        ArgumentSchema(flags=["status"], help="Target state: WORKING or DONE.", type="str"),
    ],
)
