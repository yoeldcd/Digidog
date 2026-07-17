# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `dream` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="dream",
    domain="knowledge",
    help="Use configured LLM stages to propose knowledge deltas, then confirm selected applications.",
    arguments=[
        ArgumentSchema(
            flags=["--domain"],
            default="all",
            help="Source domain: all, memory, diary, profiles, logs, or messages.",
        ),
        ArgumentSchema(
            flags=["--scope"],
            default="all",
            help="Knowledge DB scope: all, global, or local. Defaults to all.",
        ),
        ArgumentSchema(
            flags=["-l", "--limit"],
            type="int",
            default=None,
            help="Limit number of sources to inspect.",
        ),
        ArgumentSchema(
            flags=["--min-confidence"],
            type="float",
            default=None,
            help="Override minimum confidence threshold.",
        ),
        ArgumentSchema(
            flags=["--prune"],
            action="store_true",
            help="Recreate the entire knowledge graph before running dream.",
        ),
        ArgumentSchema(flags=["-j", "--json"], action="store_true", help="Output results as JSON."),
    ],
)
