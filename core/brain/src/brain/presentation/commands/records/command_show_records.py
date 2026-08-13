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
    description="Display active local records in insertion order.",
    stdin=(),
    examples=("py {LOCAL_BRAIN_SCRIPT} show-records --json",),
    output=("Active records as text or a JSON collection.",),
    exit_codes=("0: records displayed.", "1: record store could not be read."),
    safeguards=("Read-only operation; does not alter records.",),
    notes=("Deleted records are omitted from the default listing.",),
)
# Parser schema for ``show-records`` and ``show-policies``.
