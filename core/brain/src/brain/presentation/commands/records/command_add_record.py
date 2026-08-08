"""Declare the CLI contract for creating one always-on local record.

The canonical command owns the policy-oriented spelling through argparse aliases;
no parallel policy command module or action exists.
"""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="add-record",
    aliases=["registre-policie"],
    domain="records",
    help="Persist an always-on local record.",
    arguments=[
        ArgumentSchema(flags=["text"], help="Live context text to persist."),
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help="Output the created record as JSON.",
        ),
    ],
)
# Parser schema for ``add-record`` and ``registre-policie``.
