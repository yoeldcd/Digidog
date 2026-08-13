"""Command metadata for `list-pictures`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="list-pictures",
    help="List or search registered pictures.",
    domain="pictures",
    description="List or search registered pictures and their stored descriptions.",
    stdin=(),
    examples=(
        "py {LOCAL_BRAIN_SCRIPT} list-pictures --domain products --limit 25 --json",
    ),
    output=(
        "Matching picture records with identifiers, paths, domains, and descriptions.",
    ),
    exit_codes=(
        "0: matching records listed.",
        "1: filters are invalid or the registry cannot be read.",
    ),
    safeguards=("This read-only query limits results to 1 through 500 records.",),
    notes=("Deleted records are excluded unless --all is supplied.",),
    arguments=[
        ArgumentSchema(
            flags=["--id"], default="", help="Return one exact picture identifier."
        ),
        ArgumentSchema(
            flags=["--domain"],
            default="",
            help="Filter one folder-derived domain subtree.",
        ),
        ArgumentSchema(
            flags=["--query"],
            default="",
            help="Search filename, path, domain, and description.",
        ),
        ArgumentSchema(
            flags=["--all"],
            action="store_true",
            help="Include deleted/inactive records.",
        ),
        ArgumentSchema(
            flags=["--limit"],
            type="int",
            default=100,
            help="Maximum records from 1 to 500.",
        ),
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help="Render machine-readable JSON.",
        ),
    ],
)
