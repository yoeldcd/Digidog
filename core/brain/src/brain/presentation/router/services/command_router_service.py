# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command dispatch service for parsed Brain CLI arguments."""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from typing import TypeAlias, cast

from brain.application.memory.paths import BrainStoreError
from brain.infrastructure.avatar.configuration.avatar_config import load_avatar_config
from brain.infrastructure.voice.messaging.voice_signals import VoiceSignalService
from brain.presentation.actions.registry import get_action_handler
from brain.presentation.json_renderer import render_json
from brain.presentation.router.services.command_show_policy import (
    CommandShowPolicy,
    command_show_policy,
)
from brain.presentation.router.services.narration_policy import (
    CommandNarration,
    narration_for,
)


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list['JsonValue'] | dict[str, 'JsonValue']


class _MirroredCapture(io.TextIOBase):
    """Mirror CLI output to its original stream while retaining narration facts."""

    def __init__(self, target: io.TextIOBase, capture: io.StringIO) -> None:
        """Initialize the mirrored target stream and its in-memory capture.

        Args:
            target: Original CLI stream that continues to receive output.
            capture: Buffer that retains output for narration review.
        """
        self._target = target
        self._capture = capture

    def write(self, text: str) -> int:
        """Mirror text to the original stream while retaining it for narration.

        Args:
            text: Captured CLI output fragment.

        Returns:
            int: Characters written to the original stream.
        """
        self._capture.write(text)
        return self._target.write(text)

    def flush(self) -> None:
        """Flush the original mirrored output stream."""
        self._target.flush()


def dispatch_command(args: argparse.Namespace) -> int:
    """Resolve and execute the action matching parsed command arguments.

    Args:
        args: Parsed CLI arguments.

    Returns:
        int: Handler process exit code.

    Raises:
        BrainStoreError: If the requested command has no registered handler.
    """
    command_name = _command_name(args)
    action_handler = get_action_handler(command_name=command_name)

    if action_handler is None:
        raise BrainStoreError(f"Unknown command: {command_name}")

    if getattr(args, "json", False):
        return _dispatch_json(
            command_name=command_name,
            action_handler=action_handler,
            args=args,
        )

    voice_service = VoiceSignalService()
    show_policy, narration = _resolve_presentation_policy(command_name, args)

    if narration is None:
        exit_code = action_handler(args)
        _sync_successful_task(voice_service, command_name, args, exit_code)
        return exit_code

    _emit_start_review(
        voice_service=voice_service,
        command_name=command_name,
        narration=narration,
        args=args,
        show_policy=show_policy,
    )
    captured = io.StringIO()

    try:
        with (
            redirect_stdout(_MirroredCapture(sys.stdout, captured)),
            redirect_stderr(_MirroredCapture(sys.stderr, captured)),
        ):
            exit_code = action_handler(args)
    except Exception as exc:
        _emit_output_review(
            voice_service=voice_service,
            command_name=command_name,
            narration=narration,
            args=args,
            output=captured.getvalue(),
            succeeded=False,
            cause=str(exc),
            show_policy=show_policy,
        )
        raise

    _sync_successful_task(voice_service, command_name, args, exit_code)
    captured_output = captured.getvalue()
    narration_output = getattr(args, "narration_output", captured_output)
    failure_cause = _failure_cause(captured_output, exit_code)
    _emit_output_review(
        voice_service=voice_service,
        command_name=command_name,
        narration=narration,
        args=args,
        output=narration_output,
        succeeded=exit_code == 0,
        cause=failure_cause,
        show_policy=show_policy,
    )

    return exit_code


def _dispatch_json(
    command_name: str,
    action_handler: Callable[[argparse.Namespace], int],
    args: argparse.Namespace,
) -> int:
    """Execute one command and guarantee a single JSON document on stdout.

    Args:
        command_name: Registered name of the action being executed.
        action_handler: Function that executes the parsed action arguments.
        args: Parsed CLI arguments.

    Returns:
        int: Handler process exit code, or one for synthesized JSON failures.
    """
    voice_service = VoiceSignalService()
    show_policy, narration = _resolve_presentation_policy(command_name, args)
    _emit_start_review(
        voice_service=voice_service,
        command_name=command_name,
        narration=narration,
        args=args,
        show_policy=show_policy,
    )
    captured = io.StringIO()

    try:
        with redirect_stdout(captured):
            exit_code = action_handler(args)
    except Exception as exc:
        if narration:
            _emit_output_review(
                voice_service=voice_service,
                command_name=command_name,
                narration=narration,
                args=args,
                output=captured.getvalue(),
                succeeded=False,
                cause=str(exc),
                show_policy=show_policy,
            )
        raise

    output = captured.getvalue()

    if getattr(args, "raw_document_output", False):
        print(output, end="")
        _sync_successful_task(voice_service, command_name, args, exit_code)
        return exit_code

    payload, has_semantic_payload = _resolve_json_payload(
        args,
        command_name,
        output,
        exit_code,
    )
    print(render_json(payload=payload, color_enabled=getattr(args, "color", False)))

    if not has_semantic_payload:
        return 1 if exit_code == 0 else exit_code

    _sync_successful_task(voice_service, command_name, args, exit_code)

    if narration:
        narration_output = getattr(args, "narration_output", output)
        failure_cause = _failure_cause(_plain_text(output), exit_code)
        _emit_output_review(
            voice_service=voice_service,
            command_name=command_name,
            narration=narration,
            args=args,
            output=narration_output,
            succeeded=exit_code == 0,
            cause=failure_cause,
            show_policy=show_policy,
        )

    return exit_code


def _command_name(args: argparse.Namespace) -> str:
    """Return the requested command name, defaulting to the help action.

    Args:
        args: Parsed CLI arguments that may omit a command name.

    Returns:
        str: Requested command name or ``"help"`` when omitted.
    """
    command_name: str | None = getattr(args, "command", None)

    return command_name if command_name is not None else "help"


def _resolve_presentation_policy(
    command_name: str,
    args: argparse.Namespace,
) -> tuple[CommandShowPolicy | None, CommandNarration | None]:
    """Resolve the allowed voice policy and its narration for one command.

    Args:
        command_name: Registered name of the action being executed.
        args: Parsed CLI arguments that control speech suppression.

    Returns:
        tuple[CommandShowPolicy | None, CommandNarration | None]: Command
        show policy and narration, or two ``None`` values when speech is
        suppressed or unavailable.
    """
    if getattr(args, "no_speak", False):
        return None, None

    show_policy = command_show_policy(command_name, load_avatar_config())

    if show_policy is None:
        return None, None

    narration = narration_for(command=command_name, args=args)

    return show_policy, narration


def _emit_start_review(
    voice_service: VoiceSignalService,
    command_name: str,
    narration: CommandNarration | None,
    args: argparse.Namespace,
    show_policy: CommandShowPolicy | None,
) -> None:
    """Emit a call-phase voice review when the narration requests one.

    Args:
        voice_service: Service that sends reviewed voice signals.
        command_name: Registered name of the action being executed.
        narration: Optional narration selected for the command.
        args: Parsed CLI arguments forwarded to the voice service.
        show_policy: Optional presentation policy that permits the narration.
    """
    if narration is None or not narration.announce_start:
        return

    voice_service.emit_reviewed(
        command=command_name,
        phase="call",
        narration=narration,
        args=args,
        show_policy=show_policy,
    )


def _emit_output_review(
    voice_service: VoiceSignalService,
    command_name: str,
    narration: CommandNarration,
    args: argparse.Namespace,
    output: str,
    succeeded: bool,
    cause: str,
    show_policy: CommandShowPolicy | None,
) -> None:
    """Emit an output-phase review using captured command execution facts.

    Args:
        voice_service: Service that sends reviewed voice signals.
        command_name: Registered name of the action being executed.
        narration: Narration selected for the command.
        args: Parsed CLI arguments forwarded to the voice service.
        output: Captured or overridden command output for the review.
        succeeded: Whether command execution completed successfully.
        cause: Failure explanation, or an empty string after success.
        show_policy: Optional presentation policy that permits the narration.
    """

    voice_service.emit_reviewed(
        command=command_name,
        phase="output",
        narration=narration,
        args=args,
        output=output,
        succeeded=succeeded,
        cause=cause,
        show_policy=show_policy,
    )


def _sync_successful_task(
    voice_service: VoiceSignalService,
    command_name: str,
    args: argparse.Namespace,
    exit_code: int,
) -> None:
    """Synchronize task state only after a successful command execution.

    Args:
        voice_service: Service that synchronizes task state.
        command_name: Registered name of the action being executed.
        args: Parsed CLI arguments forwarded to the voice service.
        exit_code: Process exit code returned by the action handler.
    """

    if exit_code != 0:
        return

    voice_service.sync_task_state(command_name, args)


def _resolve_json_payload(
    args: argparse.Namespace,
    command_name: str,
    output: str,
    exit_code: int,
) -> tuple[JsonValue, bool]:
    """Resolve the semantic payload or synthesize a JSON error payload.

    Args:
        args: Parsed CLI arguments that may hold a semantic JSON payload.
        command_name: Registered name of the action being executed.
        output: Captured standard output from the action handler.
        exit_code: Process exit code returned by the action handler.

    Returns:
        tuple[JsonValue, bool]: Renderable payload and whether it was
        supplied by the handler or action arguments rather than synthesized
        after failure.
    """

    if _is_json_document(output):
        return cast(JsonValue, json.loads(output)), True

    if hasattr(args, "json_payload"):
        return cast(JsonValue, args.json_payload), True

    error_message = _plain_text(output).strip()

    if exit_code == 0:
        error_message = "Command did not provide a semantic JSON payload."

    return (
        {
            "ok": False,
            "command": command_name,
            "error": error_message or "Command failed without an error description.",
        },
        False,
    )


def _failure_cause(output: str, exit_code: int) -> str:
    """Return the output-derived failure explanation for a command result.

    Args:
        output: Captured command output that may explain a failure.
        exit_code: Process exit code returned by the action handler.

    Returns:
        str: Empty text after success, otherwise output text or an exit-code note.
    """

    if exit_code == 0:
        return ""

    return output.strip() or f"exit code {exit_code}"


def _is_json_document(output: str) -> bool:
    """Return whether output contains exactly one valid JSON document.

    Args:
        output: Captured standard output to validate.

    Returns:
        bool: Whether the output can be decoded as a JSON document.
    """

    if not output.strip():
        return False

    try:
        json.loads(output)
    except json.JSONDecodeError:
        return False

    return True


def _plain_text(output: str) -> str:
    """Remove terminal ANSI sequences from a captured error message.

    Args:
        output: Text that may contain ANSI terminal control sequences.

    Returns:
        str: Output text with ANSI terminal control sequences removed.
    """
    
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)
