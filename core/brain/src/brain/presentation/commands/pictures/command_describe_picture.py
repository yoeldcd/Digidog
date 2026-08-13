"""Command metadata for `describe-image`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="describe-image",
    help="Describe registered images using text or img2text.",
    aliases=["describe-picture"],
    domain="pictures",
    description="Describe registered images with manual text or img2text generation.",
    stdin=(),
    examples=(
        'py {LOCAL_BRAIN_SCRIPT} describe-image pic12 "Pink puppy beside a laptop" --json',
    ),
    output=("Updated picture identifiers and descriptions, as text or JSON.",),
    exit_codes=(
        "0: requested descriptions saved.",
        "1: selection, generation, or persistence failed.",
    ),
    safeguards=(
        "Bulk modes operate only on active records; --undescribed skips records that already have text.",
    ),
    notes=(
        "Omitting manual text requests img2text generation; --prompt overrides its prompt.",
    ),
    arguments=[
        ArgumentSchema(
            flags=["picture_id"],
            nargs="?",
            default="",
            help="Registered picture identifier.",
        ),
        ArgumentSchema(
            flags=["description"],
            nargs="?",
            default="",
            help="Manual description; omit for img2text.",
        ),
        ArgumentSchema(
            flags=["--all"],
            action="store_true",
            help="Regenerate model descriptions for all active images.",
        ),
        ArgumentSchema(
            flags=["--undescribeds", "--undescribed"],
            action="store_true",
            help="Describe only active images whose description is empty.",
        ),
        ArgumentSchema(
            flags=["--prompt"], default="", help="Optional img2text prompt override."
        ),
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help="Render machine-readable JSON.",
        ),
    ],
)
