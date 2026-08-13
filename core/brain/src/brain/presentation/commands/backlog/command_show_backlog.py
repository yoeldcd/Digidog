# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `show-backlog` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="show-backlog",
    aliases=["task-list"],
    domain="task backlog",
    help="Display the workspace backlog tree. (e.g. show-backlog dev.db)",
    arguments=[
        ArgumentSchema(
            flags=["task_domain"],
            help="Optional domain path to filter tasks.",
            nargs="?",
            default=None,
        ),
        ArgumentSchema(
            flags=["--all"],
            action="store_true",
            help="Show all tasks (including completed ones).",
        ),
    ],
    description="Display backlog tasks as a filtered tree.",
    stdin=(),
    examples=("py {LOCAL_BRAIN_SCRIPT} show-backlog dev.db --all",),
    output=("A domain tree containing matching tasks is printed.",),
    exit_codes=("0: backlog displayed", "1: invalid domain filter"),
    safeguards=("Filtering is read-only and does not mutate backlog records.",),
    notes=("Completed tasks are hidden unless --all is provided.",),
)
