"""Command metadata for the `delete-memory-entry` CLI command."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="delete-memory-entry",
    domain="memory",
    help="Delete a specific key or an entire memory domain. (e.g. delete-memory-entry a.b.c value)",
    description="Delete one memory entry, or remove an entire domain after explicit confirmation.",
    stdin=("No stdin is read; target and confirmation are command-line arguments.",),
    examples=(
        "py {LOCAL_BRAIN_SCRIPT} delete-memory-entry project.product.note",
        "py {LOCAL_BRAIN_SCRIPT} delete-memory-entry project --confirm project",
    ),
    output=(
        "Text mode prints the deletion message; --json identifies the deleted entry/domain or returns an error object.",
    ),
    exit_codes=(
        "0: requested entry or confirmed domain deleted.",
        "1: target missing, confirmation incorrect, or deletion failed.",
    ),
    safeguards=(
        "Deleting a whole domain is refused unless --confirm exactly matches the domain; entry deletion needs no confirmation.",
    ),
    notes=(
        "A dotted domain argument is split into domain and key when it is not an existing directory.",
    ),
    arguments=[
        ArgumentSchema(
            flags=["domain"], help="The memory domain or subdomain name (e.g. domain)."
        ),
        ArgumentSchema(
            flags=["key"],
            default=None,
            required=False,
            nargs="?",
            help="The key to delete. If omitted, deletes the entire memory domain.",
        ),
        ArgumentSchema(
            flags=["-co", "--confirm"],
            default="",
            help="Must match the memory domain name to confirm recursive deletion.",
        ),
        ArgumentSchema(
            flags=["-j", "--json"], action="store_true", help="Output result as JSON."
        ),
    ],
)
