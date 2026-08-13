# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `create-brain` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="create-brain",
    domain="general",
    help="Create a local Brain consumer in a target workspace using core/core_cli.py. (e.g. create-brain <workspace-root>)",
    arguments=[
        ArgumentSchema(
            flags=["--workspace", "-w"],
            help="Target workspace root path.",
            required=False,
            type="str",
        ),
        ArgumentSchema(
            flags=["workspace_path"],
            help="Target workspace root path (compact positional form).",
            nargs="?",
            default=None,
        ),
        ArgumentSchema(
            flags=["--limit", "-l"],
            help="Limit the number of migrated files logged to the terminal.",
            type="int",
            default=10,
        ),
    ],
    description="Create a Brain consumer in the target workspace using the core bootstrap utility.",
    stdin=("No stdin is consumed; provide the workspace path as an argument.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} create-brain D:\\work\\project",),
    output=("Bootstrap progress and migrated-file summary.",),
    exit_codes=(
        "0 when the consumer is created; nonzero when the target is invalid or setup fails.",
    ),
    safeguards=(
        "The target path is validated before files are created; existing files are not blindly removed.",
    ),
    notes=("Use --limit to cap migration details printed in the terminal.",),
)
