# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `get-context` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="get-context",
    domain="general",
    help="Hydrate LLM context with memory indexes, available profiles, and recent diary summaries.",
    arguments=[
        ArgumentSchema(
            flags=["-ld", "--limit-diary"],
            type="int",
            default=3,
            help="Number of recent diary files to include.",
        ),
        ArgumentSchema(
            flags=["--domain"],
            type="str",
            default="",
            help="Highlight or filter logs matching the specified domain.",
        ),
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help="Print machine-readable context cards.",
        ),
    ],
    description="Build a context-hydration payload from indexes, profiles, logs, and recent diary entries.",
    stdin=("No stdin is consumed.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} get-context --domain engineering --json",),
    output=("Context cards and index summaries, optionally as JSON.",),
    exit_codes=(
        "0 when context is assembled; nonzero if a requested source cannot be read.",
    ),
    safeguards=("Read-only aggregation; limit-diary bounds diary loading.",),
    notes=(
        "The domain option highlights matching log entries rather than changing stored data.",
    ),
)
