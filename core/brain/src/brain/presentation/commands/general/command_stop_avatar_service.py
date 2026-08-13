# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for `stop-avatar-service`."""

from brain.presentation.commands.models import CommandSchema

SCHEMA = CommandSchema(
    name="stop-avatar-service",
    domain="general",
    help="Gracefully stop the avatar service.",
    arguments=[],
    description="Request a graceful shutdown of the detached avatar service.",
    stdin=("No stdin is consumed.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} stop-avatar-service",),
    output=("Shutdown acknowledgement and final service state.",),
    exit_codes=(
        "0 when stopped or already absent; nonzero when shutdown cannot be requested.",
    ),
    safeguards=(
        "Only the local avatar service is targeted; no message records are deleted.",
    ),
    notes=("A stopped service can be started again with start-avatar-service.",),
)
