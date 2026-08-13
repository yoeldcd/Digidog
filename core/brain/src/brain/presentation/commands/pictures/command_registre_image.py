"""Command metadata for `registre-image`."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="registre-image",
    aliases=[],
    domain="pictures",
    help="Register one image from a file or base64 data in a selected picture scope.",
    arguments=[
        ArgumentSchema(
            flags=["--image-file"],
            required=False,
            default="",
            help="Full path to the source image file.",
        ),
        ArgumentSchema(
            flags=["--image-data"],
            required=False,
            default="",
            help="Raw base64 or data-URL image content.",
        ),
        ArgumentSchema(
            flags=["--scope"],
            required=True,
            help="Picture scope: local or global.",
        ),
        ArgumentSchema(
            flags=["--domain"],
            required=True,
            help="Dotted picture domain (for example a.b.c).",
        ),
        ArgumentSchema(
            flags=["--description"],
            default="",
            help="Optional Markdown description; omitted value requests the standard image-to-text semantic fields.",
        ),
        ArgumentSchema(
            flags=["--index"],
            action="store_true",
            help="Refresh semantic picture references after registration.",
        ),
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help="Render machine-readable JSON.",
        ),
    ],
    description="Register one image from a file or base64 payload in the selected picture scope.",
    stdin=(),
    examples=(
        "py {LOCAL_BRAIN_SCRIPT} registre-image --image-file image.png --scope local --domain project",
    ),
    output=("Registered picture identifier and metadata.",),
    exit_codes=(
        "0: image registered.",
        "1: invalid source, scope, or persistence failure.",
    ),
    safeguards=(
        "Requires exactly one image source and validates scope before writing.",
    ),
    notes=("--index refreshes semantic picture references after registration.",),
)
