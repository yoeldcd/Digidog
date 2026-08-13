"""Command metadata for `set-picture-guidance`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="set-picture-guidance",
    domain="pictures",
    help="Create or update one img2text tag or known character description.",
    arguments=[
        ArgumentSchema(
            flags=["section"], help="Target `tags` or `characters` section."
        ),
        ArgumentSchema(flags=["name"], help="Tag label or known character name."),
        ArgumentSchema(
            flags=["description"], help="Observable identification criteria."
        ),
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help="Render machine-readable JSON.",
        ),
    ],
    description="Create or update one img2text tag or known-character guidance entry.",
    stdin=(),
    examples=(
        'py {LOCAL_BRAIN_SCRIPT} set-picture-guidance tags portrait "front-facing portrait"',
    ),
    output=("Updated guidance entry and its normalized section/name.",),
    exit_codes=(
        "0: guidance saved.",
        "1: invalid section, name, or persistence failure.",
    ),
    safeguards=("Validates section and non-empty guidance fields before writing.",),
    notes=("Guidance is consumed by subsequent picture description operations.",),
)
