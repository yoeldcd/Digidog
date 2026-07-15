"""Command metadata for the `edit-diary` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="edit-diary",
    domain="diary",
    help="Edit an existing entry in the diary domain.",
    arguments=[
        ArgumentSchema(flags=["-dt", "--datetime"], required=False, help="The exact timestamp of the entry to edit (e.g. '27-06-2026 23:28:51')."),
        ArgumentSchema(flags=["-t", "--title"], required=False, help="New title for the diary entry."),
        ArgumentSchema(flags=["-tx", "--text"], required=False, help="Overwrite the entry's text content entirely."),
        ArgumentSchema(flags=["-a", "--append"], required=False, help="Append text to the entry's current content."),
        ArgumentSchema(flags=["-r", "--replace"], required=False, help="Text to find and replace in the entry."),
        ArgumentSchema(flags=["-w", "--with-text"], required=False, help="The text to replace it with (requires --replace)."),
        ArgumentSchema(flags=["timestamp"], nargs="?", default=None, help="The exact timestamp of the entry to edit (compact positional form)."),
        ArgumentSchema(flags=["body"], nargs="?", default=None, help="Replacement entry text (compact positional form)."),
    ],
)
