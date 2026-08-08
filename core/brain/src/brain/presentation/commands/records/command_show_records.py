"""Declare the CLI contract for listing always-on local records.

The policy-oriented spelling is a parser alias of the canonical record command,
not an independent command identity.
"""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="show-records",
    aliases=["show-policies"],
    domain="records",
    help="Show all active local records.",
    arguments=[
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help="Output active records as JSON.",
        ),
    ],
)
# Parser schema for ``show-records`` and ``show-policies``.
