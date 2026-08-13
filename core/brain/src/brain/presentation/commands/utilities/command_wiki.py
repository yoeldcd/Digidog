# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the core-owned Documentation Utils wrapper."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="wiki",
    domain="utilities",
    help="Check, generate, or serve a documentation wiki through core Documentation Utils.",
    arguments=[
        ArgumentSchema(
            flags=["mode"], help="Wiki operation: check, generate, or serve."
        ),
        ArgumentSchema(
            flags=["documentation_path"], help="Documentation directory path."
        ),
        ArgumentSchema(
            flags=["--log-domain"],
            required=False,
            help="Optional top-level log domain.",
        ),
        ArgumentSchema(
            flags=["--host"], required=False, default="127.0.0.1", help="Serve host."
        ),
        ArgumentSchema(
            flags=["--port"],
            required=False,
            type="int",
            default=4173,
            help="Serve port.",
        ),
    ],
    description="Check, generate, or serve documentation wiki content for a selected directory.",
    stdin=(),
    examples=(
        "py {LOCAL_BRAIN_SCRIPT} wiki check documentation",
        "py {LOCAL_BRAIN_SCRIPT} wiki serve documentation --port 4173",
    ),
    output=("Wiki validation, generation summary, or serving address.",),
    exit_codes=(
        "0: requested wiki operation completed.",
        "1: documentation path or operation failed.",
    ),
    safeguards=(
        "Generation targets the supplied documentation directory; check mode is read-only.",
    ),
    notes=("Serve mode binds the configured host and port until stopped.",),
)
