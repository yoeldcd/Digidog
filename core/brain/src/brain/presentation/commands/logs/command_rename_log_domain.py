"""Command metadata for renaming one log domain subtree."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="rename-log-domain",
    domain="logs",
    help="Rename a log domain and its descendants.",
    description="Rename a domain across every log entry that currently uses the old domain.",
    stdin=(
        "No stdin is read; provide old and new domain names as positional arguments.",
    ),
    examples=("py {LOCAL_BRAIN_SCRIPT} rename-log-domain project product",),
    output=(
        "Updates matching entries and reports the number renamed; --json emits structured status.",
    ),
    exit_codes=(
        "0: domain rename completed.",
        "2: old or new domain is invalid, or log files cannot be updated.",
    ),
    safeguards=(
        "Only exact domain matches are changed; other domain names and entry fields remain intact.",
    ),
    notes=(
        "Renaming is persistent and applies to all matching entries, not just the index.",
    ),
    arguments=[
        ArgumentSchema(flags=["source"], help="Existing log domain path."),
        ArgumentSchema(flags=["target"], help="Replacement log domain path."),
        ArgumentSchema(
            flags=["--exact"],
            action="store_true",
            help="Rename only direct entries, excluding descendants.",
        ),
    ],
)
