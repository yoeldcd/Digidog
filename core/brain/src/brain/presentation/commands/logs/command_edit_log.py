# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `edit-log` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="edit-log",
    domain="logs",
    help="Edit an existing log entry in a workspace log file.",
    arguments=[
        ArgumentSchema(flags=["-dt", "--datetime"], required=False, help="The exact timestamp of the entry to edit (e.g. '27-06-2026 01:38 am')."),
        ArgumentSchema(flags=["-d", "--log-domain", "--domain"], required=False, help="New log domain for the entry."),
        ArgumentSchema(flags=["-t", "--title"], required=False, help="New title for the entry."),
        ArgumentSchema(flags=["-ty", "--type"], required=False, help="New type of change (feature, fix, refactor, performance, improvement, documentation)."),
        ArgumentSchema(flags=["-w", "--why"], required=False, help="New reason/motivation for the change."),
        ArgumentSchema(flags=["-dx", "--desc"], required=False, help="New description of the change (supports multiline)."),
        ArgumentSchema(flags=["-i", "--impact"], required=False, help="New impact of the change (supports multiline)."),
        ArgumentSchema(flags=["timestamp"], nargs="?", default=None, help="The exact timestamp of the entry to edit (compact positional form)."),
        ArgumentSchema(flags=["domain"], nargs="?", default=None, help="New log domain for the entry (compact positional form)."),
        ArgumentSchema(flags=["compact_title"], nargs="?", default=None, help="New title for the entry (compact positional form)."),
        ArgumentSchema(flags=["compact_type"], nargs="?", default=None, help="New type of change (compact positional form)."),
        ArgumentSchema(flags=["compact_why"], nargs="?", default=None, help="New reason/motivation for the change (compact positional form)."),
        ArgumentSchema(flags=["compact_desc"], nargs="?", default=None, help="New description of the change (compact positional form)."),
        ArgumentSchema(flags=["compact_impact"], nargs="?", default=None, help="New impact of the change (compact positional form)."),
    ],
)
