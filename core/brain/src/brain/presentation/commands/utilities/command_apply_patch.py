# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the guarded repository patch applicator."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


SCHEMA = CommandSchema(
    name="apply-patch",
    domain="utilities",
    help="Apply a validated exact-text patch specification received through standard input.",
    arguments=[
        ArgumentSchema(
            flags=["--check"],
            action="store_true",
            help="Validate and report the complete patch without writing files.",
        ),
    ],
)