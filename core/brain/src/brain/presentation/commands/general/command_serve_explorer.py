# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `serve-explorer` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="serve-explorer",
    domain="general",
    help="Serve the static Brain Explorer UI and local JSON API.",
    arguments=[
        ArgumentSchema(flags=["--host"], default="127.0.0.1", help="HTTP host to bind. Defaults to 127.0.0.1."),
        ArgumentSchema(flags=["--port"], type="int", default=8127, help="HTTP port to bind. Defaults to 8127."),
        ArgumentSchema(
            flags=["--api-timeout"],
            type="float",
            default=30.0,
            help="Maximum seconds allowed for one delegated brain CLI API call.",
        ),
    ],
)
