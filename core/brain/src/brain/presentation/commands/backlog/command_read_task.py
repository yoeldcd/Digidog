# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `read-task` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="read-task",
    domain="task backlog",
    help="Read and display a specific task from the backlog by ID or number. (e.g. read-task t749 or read-task --id 749)",
    arguments=[
        ArgumentSchema(
            flags=["task_id"],
            nargs="?",
            default="",
            help="Task ID or number to read (e.g. t749 or 749).",
            type="str",
        ),
        ArgumentSchema(
            flags=["--id"],
            required=False,
            default="",
            help="Task ID or number to read (e.g. t749 or 749).",
        ),
    ],
)
