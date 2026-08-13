"""Command metadata for the `export` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="export",
    domain="memory",
    help="Export a memory domain or the entire memory store. (e.g. export profile --out backup/)",
    description="Copy one memory domain or every domain into a destination directory.",
    stdin=(
        "No stdin is consumed; --out or the compact positional destination is required.",
    ),
    examples=(
        "py {LOCAL_BRAIN_SCRIPT} export profile --out backup",
        "py {LOCAL_BRAIN_SCRIPT} export all backup",
    ),
    output=(
        "Prints the resolved destination and exported domain; the action also records a JSON payload for the router.",
    ),
    exit_codes=(
        "0: files copied successfully.",
        "1: destination is missing or export fails.",
    ),
    safeguards=(
        "The destination is created with parents, and a missing named domain raises an error before copying.",
    ),
    notes=(
        "The default domain is all, but a destination must still be supplied via --out or positional out_dir.",
    ),
    arguments=[
        ArgumentSchema(
            flags=["domain"], default="all", help='Memory domain name or "all".'
        ),
        ArgumentSchema(
            flags=["-o", "--out"], required=False, help="Destination directory path."
        ),
        ArgumentSchema(
            flags=["out_dir"],
            nargs="?",
            default=None,
            help="Destination directory path (compact positional form).",
        ),
    ],
)
