# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `knowledge-init` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="knowledge-init",
    domain="knowledge",
    help="Initialize the private knowledge graph runtime and SQLite schema.",
    description="Create the knowledge SQLite schema for the selected scope; --reset recreates it after confirmation.",
    stdin=(
        "No stdin is read. Scope, reset, confirmation, and output mode come from command-line flags.",
    ),
    examples=("py {LOCAL_BRAIN_SCRIPT} knowledge-init --scope local",),
    output=(
        "Text reports initialization for each selected scope. --json emits the same outcome as structured JSON.",
    ),
    exit_codes=(
        "0: schema initialization or confirmed reset completed.",
        "2: invalid scope/options or initialization failed.",
    ),
    safeguards=(
        "Without --yes, --reset asks for confirmation before deleting the selected database.",
    ),
    notes=(
        "Default scope is all; without --reset, existing tables are preserved and missing schema is created.",
    ),
    arguments=[
        ArgumentSchema(
            flags=["--reset"],
            action="store_true",
            help="Delete and recreate the private knowledge database.",
        ),
        ArgumentSchema(
            flags=["--scope"],
            default="all",
            help="Knowledge DB scope: all, global, or local. Defaults to all.",
        ),
        ArgumentSchema(
            flags=["-y", "--yes"], action="store_true", help="Skip reset confirmation."
        ),
        ArgumentSchema(
            flags=["-j", "--json"], action="store_true", help="Output results as JSON."
        ),
    ],
)
