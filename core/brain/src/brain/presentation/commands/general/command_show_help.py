# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the `help` CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="help",
    domain="general",
    help="Show memory store help.",
    arguments=[
        ArgumentSchema(
            flags=["topic"],
            nargs="?",
            default=None,
            help="Optional command name to inspect.",
        ),
        ArgumentSchema(
            flags=["--short"],
            action="store_true",
            help="Show only domains and command names.",
        ),
    ],
    description="Display command and domain help, optionally narrowed to one topic.",
    stdin=("No stdin is consumed.",),
    examples=("py {LOCAL_BRAIN_SCRIPT} help query",),
    output=("Human-readable command documentation; --short emits a compact index.",),
    exit_codes=("0 when help is rendered; nonzero for an unknown topic.",),
    safeguards=("Read-only documentation lookup.",),
    notes=("The topic is optional and may be a command name.",),
)
