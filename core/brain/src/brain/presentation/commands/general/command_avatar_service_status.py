# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for `avatar-service-status`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="avatar-service-status",
    domain="general",
    help="Show avatar service state, retained messages, and presentation errors.",
    arguments=[
        ArgumentSchema(
            flags=["--color"],
            action="store_true",
            help="Use ANSI colors for human-readable output.",
        )
    ],
    description="Report the local avatar service state and retained delivery diagnostics.",
    stdin=("No stdin is consumed.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} avatar-service-status --color",),
    output=("Service status, message counts, and presentation errors.",),
    exit_codes=(
        "0 when status is read; nonzero if the status store cannot be accessed.",
    ),
    safeguards=("Read-only operation; it does not start or stop the service.",),
    notes=("ANSI colors are emitted only when --color is supplied.",),
)
