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
        ArgumentSchema(flags=["mode"], help="Wiki operation: check, generate, or serve."),
        ArgumentSchema(flags=["documentation_path"], help="Documentation directory path."),
        ArgumentSchema(flags=["--log-domain"], required=False, help="Optional top-level log domain."),
        ArgumentSchema(flags=["--host"], required=False, default="127.0.0.1", help="Serve host."),
        ArgumentSchema(flags=["--port"], required=False, type="int", default=4173, help="Serve port."),
    ],
)
