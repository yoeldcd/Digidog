"""Command metadata for `delete-picture-guidance`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="delete-picture-guidance",
    help="Delete configured picture guidance.",
    domain="pictures",
    description="Delete one configured img2text tag or known-character description.",
    stdin=(),
    examples=("py {LOCAL_BRAIN_SCRIPT} delete-picture-guidance tags portrait --json",),
    output=("Deletion confirmation with the removed section and guidance name.",),
    exit_codes=(
        "0: guidance deleted.",
        "1: section or name is invalid, absent, or cannot be persisted.",
    ),
    safeguards=(
        "Deletes only the explicitly named entry from the tags or characters section.",
    ),
    notes=("List the section first when the exact stored guidance name is uncertain.",),
    arguments=[
        ArgumentSchema(
            flags=["section"], help="Target `tags` or `characters` section."
        ),
        ArgumentSchema(
            flags=["name"], help="Existing tag label or known character name."
        ),
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help="Render machine-readable JSON.",
        ),
    ],
)
