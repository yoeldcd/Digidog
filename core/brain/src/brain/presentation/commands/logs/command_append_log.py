# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `append-log` CLI command."""

from __future__ import annotations

from brain.application.logs.entry_formatting import valid_log_types_text
from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="append-log",
    domain="logs",
    help="Append a new log entry to the agent logs of the workspace.",
    description="Create a timestamped log entry with domain, title, type, rationale, description, and impact.",
    stdin=(
        "No stdin is read; provide fields as options or compact positional arguments.",
    ),
    examples=(
        (
            'py {LOCAL_BRAIN_SCRIPT} append-log project "Release" feature --why "Ship" '
            '--desc "Released" --impact "Users benefit"'
        ),
    ),
    output=(
        "Writes the new entry to the agent log and reports its timestamp; --json returns structured status.",
    ),
    exit_codes=(
        "0: entry appended.",
        "2: required fields, timestamp, or log type are invalid.",
    ),
    safeguards=(
        "Only accepted log types are recorded; an explicit timestamp must use DD-MM-YYYY HH:mm am/pm.",
    ),
    notes=(
        "Accepted types are feature, fix, refactor, performance, improvement, documentation, and maintenance.",
    ),
    arguments=[
        ArgumentSchema(
            flags=["-d", "--log-domain", "--domain"],
            required=False,
            help="The package or subdomain affected (e.g. brain.cli).",
        ),
        ArgumentSchema(
            flags=["-t", "--title"], required=False, help="The title of the change."
        ),
        ArgumentSchema(
            flags=["-ty", "--type"],
            required=False,
            help=f"The type of change. Accepted values: {valid_log_types_text()}.",
        ),
        ArgumentSchema(
            flags=["-w", "--why"],
            required=False,
            help="The reason or motivation for the change.",
        ),
        ArgumentSchema(
            flags=["-dx", "--desc"],
            required=False,
            help="Description of the change (supports multiline).",
        ),
        ArgumentSchema(
            flags=["-i", "--impact"],
            required=False,
            help="Impact of the change (supports multiline).",
        ),
        ArgumentSchema(
            flags=["-dt", "--datetime"],
            required=False,
            help="Explicit entry timestamp in format 'DD-MM-YYYY HH:mm am/pm'.",
        ),
        ArgumentSchema(
            flags=["domain"],
            nargs="?",
            default=None,
            help="The package or subdomain affected (compact positional form).",
        ),
        ArgumentSchema(
            flags=["compact_title"],
            nargs="?",
            default=None,
            help="The title of the change (compact positional form).",
        ),
        ArgumentSchema(
            flags=["compact_type"],
            nargs="?",
            default=None,
            help=f"The type of change in compact positional form. Accepted values: {valid_log_types_text()}.",
        ),
        ArgumentSchema(
            flags=["compact_why"],
            nargs="?",
            default=None,
            help="The reason or motivation for the change (compact positional form).",
        ),
        ArgumentSchema(
            flags=["compact_desc"],
            nargs="?",
            default=None,
            help="Description of the change (compact positional form).",
        ),
        ArgumentSchema(
            flags=["compact_impact"],
            nargs="?",
            default=None,
            help="Impact of the change (compact positional form).",
        ),
    ],
)
