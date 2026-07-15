"""Command dispatch service for parsed Brain CLI arguments."""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout

from brain.application.memory.paths import BrainStoreError
from brain.presentation.actions.registry import get_action_handler
from brain.infrastructure.voice.signals import VoiceSignalService
from brain.presentation.router.services.narration_policy import narration_for


class _MirroredCapture(io.TextIOBase):
    """Mirror CLI output to its original stream while retaining narration facts."""

    def __init__(self, target: io.TextIOBase, capture: io.StringIO) -> None:
        self._target = target
        self._capture = capture

    def write(self, text: str) -> int:
        self._capture.write(text)
        return self._target.write(text)

    def flush(self) -> None:
        self._target.flush()


def dispatch_command(args: argparse.Namespace) -> int:
    """Resolve and execute the CLI action matching parsed command arguments."""
    command_name: str | None = getattr(args, "command", None)
    if command_name is None:
        command_name = "help"

    action_handler: Callable[[argparse.Namespace], int] | None = get_action_handler(command_name=command_name)
    if action_handler is None:
        raise BrainStoreError(f"Unknown command: {command_name}")

    if getattr(args, "json", False):
        return _dispatch_json(command_name=command_name, action_handler=action_handler, args=args)

    voice_service = VoiceSignalService()
    narration = None if getattr(args, "no_speak", False) else narration_for(command=command_name, args=args)
    if narration is None:
        exit_code = action_handler(args)
        if exit_code == 0:
            voice_service.sync_task_state(command_name, args)
        return exit_code
    if narration and narration.announce_start:
        voice_service.emit_reviewed(command=command_name, phase="call", narration=narration, args=args)
    captured = io.StringIO()
    try:
        with redirect_stdout(_MirroredCapture(sys.stdout, captured)), redirect_stderr(_MirroredCapture(sys.stderr, captured)):
            exit_code = action_handler(args)
    except Exception as exc:
        voice_service.emit_reviewed(
            command=command_name,
            phase="output",
            narration=narration,
            args=args,
            output=captured.getvalue(),
            succeeded=False,
            cause=str(exc),
        )
        raise
    if exit_code == 0:
        voice_service.sync_task_state(command_name, args)
    voice_service.emit_reviewed(
        command=command_name,
        phase="output",
        narration=narration,
        args=args,
        output=captured.getvalue(),
        succeeded=exit_code == 0,
        cause="" if exit_code == 0 else captured.getvalue().strip() or f"exit code {exit_code}",
    )
    return exit_code


def _dispatch_json(
    command_name: str,
    action_handler: Callable[[argparse.Namespace], int],
    args: argparse.Namespace,
) -> int:
    """Execute one command and guarantee a single JSON document on `stdout`."""
    voice_service = VoiceSignalService()
    narration = None if getattr(args, "no_speak", False) else narration_for(command=command_name, args=args)
    if narration and narration.announce_start:
        voice_service.emit_reviewed(command=command_name, phase="call", narration=narration, args=args)
    captured = io.StringIO()
    try:
        with redirect_stdout(captured):
            exit_code = action_handler(args)
    except Exception as exc:
        if narration:
            voice_service.emit_reviewed(
                command=command_name,
                phase="output",
                narration=narration,
                args=args,
                output=captured.getvalue(),
                succeeded=False,
                cause=str(exc),
            )
        raise

    output = captured.getvalue()
    if _is_json_document(output=output):
        print(output, end="" if output.endswith("\n") else "\n")
    elif hasattr(args, "json_payload"):
        print(json.dumps(args.json_payload, ensure_ascii=False, indent=2))
    else:
        error_message = _plain_text(output).strip() if exit_code != 0 else "Command did not provide a semantic JSON payload."
        payload = {
            "ok": False,
            "command": command_name,
            "error": error_message or "Command failed without an error description.",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if exit_code == 0 else exit_code

    if exit_code == 0:
        voice_service.sync_task_state(command_name, args)
    if narration:
        voice_service.emit_reviewed(
            command=command_name,
            phase="output",
            narration=narration,
            args=args,
            output=output,
            succeeded=exit_code == 0,
            cause="" if exit_code == 0 else _plain_text(output).strip() or f"exit code {exit_code}",
        )
    return exit_code


def _is_json_document(output: str) -> bool:
    """Return whether `output` contains exactly one valid JSON document."""
    if not output.strip():
        return False
    try:
        json.loads(output)
    except json.JSONDecodeError:
        return False
    return True


def _plain_text(output: str) -> str:
    """Remove terminal ANSI sequences from a captured error message."""
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)
