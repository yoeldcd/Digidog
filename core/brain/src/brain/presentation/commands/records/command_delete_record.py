"""Declare the CLI contract for deleting one always-on local record.

Both accepted spellings normalize to the canonical ``delete-record`` command
before the router selects its single record action.
"""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="delete-record",
    aliases=["deprecate-policie"],
    domain="records",
    help="Delete an always-on local record by ID.",
    arguments=[
        ArgumentSchema(
            flags=["record_id"],
            default=None,
            nargs="?",
            help="Record ID in rec## format.",
        ),
        ArgumentSchema(
            flags=["--id"],
            default=None,
            help="Record ID in rec## format.",
        ),
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help="Output the deletion result as JSON.",
        ),
    ],
)
# Parser schema for ``delete-record`` and ``deprecate-policie``.
