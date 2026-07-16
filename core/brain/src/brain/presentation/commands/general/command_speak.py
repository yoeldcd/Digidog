# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `speak` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="speak",
    aliases=["avatar-message"],
    domain="general",
    help="Present enriched Markdown through the avatar and narrate its spoken projection.",
    arguments=[
        ArgumentSchema(flags=["-tx", "--text"], required=False, help="Text to speak. Can also be passed as a positional argument."),
        ArgumentSchema(flags=["-l", "--lang"], default="es", help="Spoken language code (e.g. es, en). Defaults to es."),
        ArgumentSchema(flags=["--emotion"], default="", help="Avatar animation name resolved as avatar_{emotion}.gif."),
        ArgumentSchema(
            flags=["--codex-thread-id"],
            default="",
            help="Codex thread UUID used as the reply target for this message.",
        ),
        ArgumentSchema(flags=["body"], nargs="?", default=None, help="Text to speak in compact positional form."),
    ],
)
