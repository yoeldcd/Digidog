# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `delete-task` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="delete-task",
    domain="task backlog",
    help="Delete a DONE task, or force-delete any task. (e.g. delete-task t1 --force)",
    arguments=[
        ArgumentSchema(
            flags=["task_id"],
            help="Task ID to delete (e.g. t1 or 1).",
            type="str",
        ),
        ArgumentSchema(
            flags=["--force"],
            action="store_true",
            help="Delete a WORKING task without marking it DONE first.",
        ),
    ],
)
