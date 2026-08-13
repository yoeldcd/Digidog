# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the code symbol search tool."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="search-symbol",
    domain="utilities",
    help="Search for classes, functions, interfaces, methods, and procedures across multi-language source files.",
    arguments=[
        ArgumentSchema(
            flags=["--name"],
            required=False,
            default="",
            help="Name substring or pattern to match.",
        ),
        ArgumentSchema(
            flags=["--language"],
            required=False,
            default="",
            help="Language parser filter (python, javascript, typescript, powershell, batch, all). Inferred from extension if omitted.",
        ),
        ArgumentSchema(
            flags=["--path"],
            required=False,
            default=".",
            help="Base directory or file path to search.",
        ),
        ArgumentSchema(
            flags=["--kind"],
            required=False,
            default="all",
            help="Filter symbol kind (all, class, function, method).",
        ),
    ],
    description="Search source files for matching classes, functions, methods, or other symbols.",
    stdin=(),
    examples=("py {LOCAL_BRAIN_SCRIPT} search-symbol --name Component --path core/brain",),
    output=(
        "Matching symbol locations and metadata, optionally filtered by language and kind.",
    ),
    exit_codes=("0: search completed.", "1: invalid path, parser, or search failure."),
    safeguards=("Read-only traversal; source files are not modified.",),
    notes=("Language is inferred from extensions when --language is omitted.",),
)
