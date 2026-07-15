"""Command metadata for the `add-task` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="add-task",
    domain="task backlog",
    help="Add a task to the workspace backlog. (e.g. add-task dev.db 'Update schema' -d 'Use standard DTOs' -p HIGH)",
    arguments=[
        ArgumentSchema(
            flags=["task_domain"],
            help="Task domain path (e.g., dev.db).",
            type="str",
        ),
        ArgumentSchema(
            flags=["--title", "-t"],
            help="Task title.",
            type="str",
        ),
        ArgumentSchema(
            flags=["title_pos"],
            nargs="?",
            help="Task title (compact positional form).",
            default=None,
        ),
        ArgumentSchema(
            flags=["--description", "-d"],
            help="Task description.",
            type="str",
        ),
        ArgumentSchema(
            flags=["description_pos"],
            nargs="?",
            help="Task description (compact positional form).",
            default=None,
        ),
        ArgumentSchema(
            flags=["--priority", "-p"],
            help="Task priority level (HIGH, MEDIUM, LOW).",
            type="str",
            default="LOW",
        ),
    ],
)
