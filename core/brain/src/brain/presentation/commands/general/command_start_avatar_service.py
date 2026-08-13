# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for `start-avatar-service`."""

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="start-avatar-service",
    domain="general",
    help="Idempotently start the detached avatar service.",
    arguments=[
        ArgumentSchema(
            flags=["--mode"],
            default="dark",
            help="Avatar presentation theme: dark or light.",
        ),
    ],
    description="Start the detached avatar service using the requested presentation mode.",
    stdin=("No stdin is consumed.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} start-avatar-service --mode light",),
    output=("Service start status and process endpoint details.",),
    exit_codes=(
        "0 when already running or started successfully; nonzero on startup failure.",
    ),
    safeguards=("Startup is idempotent and validates the mode before launching.",),
    notes=("The default mode is dark.",),
)
