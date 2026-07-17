"""Command metadata for `list-pictures`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="list-pictures",
    domain="pictures",
    help="List or search registered pictures and descriptions.",
    arguments=[
        ArgumentSchema(flags=["--id"], default="", help="Return one exact picture identifier."),
        ArgumentSchema(flags=["--domain"], default="", help="Filter one folder-derived domain subtree."),
        ArgumentSchema(flags=["--query"], default="", help="Search filename, path, domain, and description."),
        ArgumentSchema(flags=["--all"], action="store_true", help="Include deleted/inactive records."),
        ArgumentSchema(flags=["--limit"], type="int", default=100, help="Maximum records from 1 to 500."),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Render machine-readable JSON."),
    ],
)
