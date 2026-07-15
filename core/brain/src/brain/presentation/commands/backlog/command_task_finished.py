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
)
