# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata schema for the `speak` CLI command.

Defines standard flags, positional text arguments, task prefixing options, and
timeout configurations. Provides usage notes, stdin guidelines, and example
invocations for avatar presentation.
"""

from __future__ import annotations

from brain.presentation.commands.models import ArgumentSchema, CommandSchema

SCHEMA = CommandSchema(
    name="speak",
    aliases=["avatar-message", "agent-message", "task-report"],
    domain="general",
    help="Present enriched Markdown through the avatar and narrate its spoken projection.",
    arguments=[
        ArgumentSchema(
            flags=["-tx", "--text"],
            required=False,
            help="Text to speak. Can also be passed as a positional argument.",
        ),
        ArgumentSchema(
            flags=["-l", "--lang"],
            default="es",
            help="Spoken language code (e.g. es, en). Defaults to es.",
        ),
        ArgumentSchema(
            flags=["--emotion"],
            default="",
            help="Avatar animation name resolved as avatar_{emotion}.gif.",
        ),
        ArgumentSchema(
            flags=["--timeout"],
            type="float",
            default=300.0,
            help=(
                "Requested finite, non-negative wait in seconds for one synchronous "
                "speech message. Effective timeout is max(--timeout, 120 + 2 * "
                "emitted characters); larger explicit values win. Defaults to 300 "
                "seconds."
            ),
        ),
        ArgumentSchema(
            flags=["--task-id"],
            default="",
            help="Prefix the message with a task report heading for the provided task ID.",
        ),
        ArgumentSchema(
            flags=["--file"],
            default="",
            help="Append one UTF-8 Markdown file to the avatar message.",
        ),
        ArgumentSchema(
            flags=["--stdin-json"],
            action="store_true",
            help=(
                "Read one JSON message envelope from standard input for a stable, "
                "policy-friendly invocation."
            ),
        ),
        ArgumentSchema(
            flags=["--codex-thread-id"],
            default="",
            help="Codex thread UUID used as the reply target for this message.",
        ),
        ArgumentSchema(
            flags=["body"],
            nargs="?",
            default=None,
            help="Text to speak in compact positional form.",
        ),
    ],
    description="Send Markdown text through the avatar presentation channel and optional speech projection.",
    stdin=(
        "With --stdin, read one JSON message envelope from standard input; otherwise stdin is ignored.",
    ),
    examples=('py {LOCAL_BRAIN_SCRIPT} speak --text "Build complete" --emotion focused',),
    output=("Avatar delivery acknowledgement and any speech/presentation status.",),
    exit_codes=(
        "0 when the message is accepted; nonzero for invalid text, file, or delivery failure.",
    ),
    safeguards=(
        "Input files are read as UTF-8; task and thread identifiers are passed through explicitly.",
    ),
    notes=("The body positional argument is a compact alternative to --text.",),
)
