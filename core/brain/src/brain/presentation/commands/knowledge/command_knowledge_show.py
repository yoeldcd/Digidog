# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `knowledge-show` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="knowledge-show",
    domain="knowledge",
    help="Show knowledge graph entities, relations, classes, or one entity.",
    description=(
        "Display one entity or list entities, relations, or classes from the selected knowledge scope."
    ),
    stdin=(
        "No stdin is read; the optional entity/filter and listing flags are command-line arguments.",
    ),
    examples=(
        'py {LOCAL_BRAIN_SCRIPT} knowledge-show "climate policy" --scope all --json',
    ),
    output=(
        "Text renders the requested entity or listing. --json emits entity, relation, or class records as structured data.",
    ),
    exit_codes=(
        "0: requested view completed, including an empty listing.",
        "2: invalid selection/filter or lookup failure.",
    ),
    safeguards=("This command is read-only and never applies pending deltas.",),
    notes=(
        "Scope defaults to global. Entity accepts an ID, name, alias, or listing filter; flags choose the row type.",
    ),
    arguments=[
        ArgumentSchema(
            flags=["entity"],
            nargs="?",
            default=None,
            help="Entity ID, canonical name, alias, or listing filter.",
        ),
        ArgumentSchema(
            flags=["--entities"],
            action="store_true",
            help="List knowledge graph entities.",
        ),
        ArgumentSchema(
            flags=["--relations"],
            action="store_true",
            help="List knowledge graph relations.",
        ),
        ArgumentSchema(
            flags=["--classes"],
            action="store_true",
            help="List registered entity classes.",
        ),
        ArgumentSchema(
            flags=["--filter"], default=None, help="Filter listed rows by text."
        ),
        ArgumentSchema(
            flags=["--scope"],
            default="global",
            help="Knowledge DB scope: all, global, or local. Defaults to global.",
        ),
        ArgumentSchema(
            flags=["-j", "--json"], action="store_true", help="Output results as JSON."
        ),
    ],
)
