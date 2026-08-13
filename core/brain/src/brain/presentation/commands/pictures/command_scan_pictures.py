"""Command metadata for `scan-images`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="scan-images",
    aliases=["scan-pictures"],
    domain="pictures",
    help="Synchronize the agent picture tree into canonical SQLite storage.",
    arguments=[
        ArgumentSchema(
            flags=["--index"],
            action="store_true",
            help="Also update reference-only picture vectors.",
        ),
        ArgumentSchema(
            flags=["--describe"],
            action="store_true",
            help="After scanning, generate descriptions only for active records whose description is empty.",
        ),
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help="Render machine-readable JSON.",
        ),
    ],
    description="Synchronize the configured picture tree into canonical SQLite records.",
    stdin=(),
    examples=("py {LOCAL_BRAIN_SCRIPT} scan-pictures --index --json",),
    output=("Scan counts and optional indexing or description results.",),
    exit_codes=(
        "0: scan completed.",
        "1: traversal, indexing, or persistence failure.",
    ),
    safeguards=(
        "Only configured picture roots are traversed; inactive records are preserved.",
    ),
    notes=("Use --describe to fill missing descriptions after scanning.",),
)
