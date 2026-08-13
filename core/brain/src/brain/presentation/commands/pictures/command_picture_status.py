"""Command metadata for `picture-status`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="picture-status",
    domain="pictures",
    help="Report picture registry, domains, descriptions, and img2text configuration.",
    arguments=[
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help="Render machine-readable JSON.",
        )
    ],
    description="Report picture registry counts, domains, descriptions, and img2text configuration.",
    stdin=(),
    examples=("py {LOCAL_BRAIN_SCRIPT} picture-status --json",),
    output=("Registry status and aggregate picture statistics.",),
    exit_codes=("0: status reported.", "1: picture registry unavailable."),
    safeguards=("Read-only status operation; no picture records are changed.",),
    notes=("Use list-pictures to inspect individual records.",),
)
