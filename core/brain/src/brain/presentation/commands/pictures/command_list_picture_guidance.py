"""Command metadata for `list-picture-guidance`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="list-picture-guidance",
    help="List configured picture guidance entries.",
    domain="pictures",
    description="List configured img2text tags and known-character recognition guidance.",
    stdin=(),
    examples=("py {LOCAL_BRAIN_SCRIPT} list-picture-guidance characters --json",),
    output=("Configured guidance entries for tags, characters, or both sections.",),
    exit_codes=(
        "0: guidance listed.",
        "1: section is invalid or guidance cannot be read.",
    ),
    safeguards=(
        "This read-only command accepts only the tags or characters section when specified.",
    ),
    notes=("Omit section to list both guidance groups.",),
    arguments=[
        ArgumentSchema(
            flags=["section"],
            nargs="?",
            default="",
            help="Optional `tags` or `characters` section.",
        ),
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help="Render machine-readable JSON.",
        ),
    ],
)
