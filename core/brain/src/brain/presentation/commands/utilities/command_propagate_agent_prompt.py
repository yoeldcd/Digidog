# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the core-owned agent prompt propagator."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="propagate-agent-prompt",
    domain="utilities",
    help="Propagate the canonical AGENTS.md to configured mirrors and direct Brain consumers.",
    arguments=[
        ArgumentSchema(flags=["--source"], required=False, help="Optional canonical prompt path override."),
        ArgumentSchema(flags=["--mirrors-file"], required=False, help="Optional mirror-list path override."),
        ArgumentSchema(flags=["--consumers-file"], required=False, help="Optional Brain consumer-registry override."),
        ArgumentSchema(flags=["--dry-run"], action="store_true", help="Validate without writing mirror files."),
    ],
)
