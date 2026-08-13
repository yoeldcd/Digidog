"""Command metadata for renaming one backlog domain subtree."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="rename-task-domain",
    domain="task backlog",
    help="Rename a backlog domain and its descendants.",
    arguments=[
        ArgumentSchema(flags=["source"], help="Existing backlog domain path."),
        ArgumentSchema(flags=["target"], help="Replacement backlog domain path."),
        ArgumentSchema(
            flags=["--exact"],
            action="store_true",
            help="Rename only direct tasks, excluding descendants.",
        ),
    ],
    description="Rename a domain path shared by backlog tasks.",
    stdin=(),
    examples=("py {LOCAL_BRAIN_SCRIPT} rename-task-domain old.domain new.domain",),
    output=("The renamed domain and affected task count are returned.",),
    exit_codes=("0: domain renamed", "1: invalid or missing domain"),
    safeguards=("Source and destination domains are validated before mutation.",),
    notes=("Task records retain their identifiers during the rename.",),
)
