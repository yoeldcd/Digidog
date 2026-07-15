"""Command metadata for the `export` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="export",
    domain="memory",
    help="Export a memory domain or the entire memory store. (e.g. export profile --out backup/)",
    arguments=[
        ArgumentSchema(flags=["domain"], default="all", help='Memory domain name or "all".'),
        ArgumentSchema(flags=["-o", "--out"], required=False, help="Destination directory path."),
        ArgumentSchema(flags=["out_dir"], nargs="?", default=None, help="Destination directory path (compact positional form)."),
    ],
)
