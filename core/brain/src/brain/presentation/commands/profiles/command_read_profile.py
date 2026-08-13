# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `read-profile` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="read-profile",
    domain="profiles",
    help="Read every Markdown entry for one agent profile in a single call.",
    arguments=[
        ArgumentSchema(
            flags=["name"],
            help="Profile name to read, for example developer, friend, or research.",
        ),
        ArgumentSchema(
            flags=["-j", "--json"],
            action="store_true",
            help="Print machine-readable profile entries.",
        ),
    ],
    description="Read the complete Markdown content for one named agent profile.",
    stdin=(),
    examples=("py {LOCAL_BRAIN_SCRIPT} read-profile developer",),
    output=("The profile Markdown, or its JSON representation with --json.",),
    exit_codes=("0: profile read.", "1: profile name is unknown or unreadable."),
    safeguards=("Resolves only the configured profile entry.",),
    notes=("Use list-profiles to discover valid names.",),
)
