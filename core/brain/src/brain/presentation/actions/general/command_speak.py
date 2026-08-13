"""Dispatch CLI speech requests and embedded Markdown presentations.

Parses command line arguments, handles standard input envelopes, and routes
narrable text or embedded Markdown files to the synchronous voice service.
Maps internal instance terminal results into compact public JSON output.
"""

# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

from __future__ import annotations

import argparse
import html
import json
import math
import sys
from pathlib import Path
from typing import Final, TypeAlias

from brain.infrastructure.voice import VoiceService
from brain.infrastructure.voice.contracts.avatar_speak_request import AvatarSpeakRequest
from brain.infrastructure.voice.contracts.instance_results import (
    InstanceTerminalResult,
    InstanceTerminalState,
)
from brain.infrastructure.voice.service.voice_service import (
    VoiceEmissionResult,
    clean_text_for_speech,
)
from brain.presentation.terminal import log_step, render_placeholders


EmbeddedMarkdown: TypeAlias = tuple[str, str]
"""Escaped filename and decoded UTF-8 Markdown content for avatar presentation."""

SYNCHRONOUS_SPEAK_TIMEOUT_SECONDS: Final[float] = 300.0
"""Default requested wait for one synchronous voice emission."""

SYNCHRONOUS_SPEAK_MINIMUM_TIMEOUT_SECONDS: Final[float] = 120.0
"""Base minimum wait for one synchronous voice emission."""

SYNCHRONOUS_SPEAK_TIMEOUT_PER_CHARACTER_SECONDS: Final[float] = 2.0
"""Additional minimum wait for each logically emitted character."""

_PUBLIC_RESPONDED_STATE: Final[str] = "RESPONDED"
"""Public state used when the internal synchronous result returns a response."""

def _effective_synchronous_timeout_seconds(
    requested_timeout_seconds: float,
    text: str,
    embedded_file: EmbeddedMarkdown | None,
) -> float:
    """Calculate the effective synchronous timeout for the logical emissions.

    Args:
        requested_timeout_seconds: User-provided finite, non-negative timeout.
        text: Text emission after any task heading has been prefixed.
        embedded_file: Optional escaped filename and decoded Markdown content.

    Returns:
        float: The requested timeout or content-sized minimum, whichever is larger.

    Raises:
        ValueError: If the requested timeout is negative or non-finite.
    """

    if not math.isfinite(requested_timeout_seconds) or requested_timeout_seconds < 0:
        raise ValueError(
            "Synchronous speak timeout must be finite and non-negative."
        )

    emitted_character_count = len(text)

    if embedded_file is not None:
        emitted_character_count += len(embedded_file[1])

    minimum_timeout_seconds = (
        SYNCHRONOUS_SPEAK_MINIMUM_TIMEOUT_SECONDS
        + SYNCHRONOUS_SPEAK_TIMEOUT_PER_CHARACTER_SECONDS * emitted_character_count
    )

    return max(requested_timeout_seconds, minimum_timeout_seconds)


def _append_terminal_result(
    terminal_results: list[InstanceTerminalResult],
    terminal_result: VoiceEmissionResult,
) -> None:
    """Append a voice result when the service returned a terminal instance.

    Args:
        terminal_results: Mutable collection of terminal results for this command.
        terminal_result: Typed value returned by a voice service operation.

    Returns:
        None.
    """

    # Type validation: verify parameter data type

    if not isinstance(terminal_result, InstanceTerminalResult):
        return

    terminal_results.append(terminal_result)


def _public_terminal_state(
    terminal_result: InstanceTerminalResult | None,
) -> str:
    """Map one internal terminal result to its compact public state.

    Args:
        terminal_result: Internal terminal result selected for the command state.

    Returns:
        str: Public response state, or SPEAKED when no reply is available.
    """

    # Conditional check: evaluate domain preconditions and invariants

    if terminal_result is None:
        return InstanceTerminalState.SPEAKED.value

    # State guard: verify lifecycle status preconditions

    if terminal_result.state is InstanceTerminalState.RESPONSED:
        return _PUBLIC_RESPONDED_STATE

    return InstanceTerminalState.SPEAKED.value


def _build_public_payload(
    terminal_result: InstanceTerminalResult | None,
    output: str,
) -> dict[str, object]:
    """Build the variable-width synchronous speak JSON payload.

    Args:
        terminal_result: Internal terminal result selected for the public state.
        output: Exact response text selected from the terminal results.

    Returns:
        dict[str, object]: Public payload with output only for RESPONDED state.
    """

    public_state = _public_terminal_state(terminal_result)
    payload: dict[str, object] = {
        "ok": True,
        "command": "speak",
        "state": public_state,
    }

    # State guard: verify lifecycle status preconditions

    if public_state == _PUBLIC_RESPONDED_STATE:
        payload["output"] = output

    else:
        payload["instruction"] = "continue"

    return payload


def _read_embedded_markdown(file_path: str) -> EmbeddedMarkdown:
    """Read one complete regular UTF-8 file before any voice work is enqueued.

    Args:
        file_path: Caller-provided path to the embedded Markdown file.

    Returns:
        EmbeddedMarkdown: Escaped filename and complete decoded UTF-8 content.

    Raises:
        ValueError: If the path is not a regular file or is not valid UTF-8.
    """

    path = Path(file_path).expanduser()

    # Conditional check: evaluate domain preconditions and invariants

    if not path.is_file():
        raise ValueError(f"Embedded file is not a regular file: {file_path}")

    # Exception safety: execute operation within error boundary

    try:
        content = path.read_bytes()

        return html.escape(path.name, quote=True), content.decode("utf-8")

    # Failure recovery: handle execution or transport exception

    except UnicodeDecodeError as exc:
        raise ValueError(f"Embedded file must be valid UTF-8: {file_path}") from exc


def handle(args: argparse.Namespace) -> int:
    """Enqueue parsed speech text or repeat the last dialogue.

    Args:
        args: Parsed text, language, emotion, embedded-file, and output flags.

    Returns:
        int: Zero when speech request was accepted; otherwise one.
    """

    color_enabled = getattr(args, "color", False)

    # Exception safety: execute operation within error boundary

    try:
        text = args.text

        # Content check: validate message text payload

        if text is None:
            text = args.body

        lang = getattr(args, "lang", "es")
        emotion = getattr(args, "emotion", "")
        codex_thread_id = getattr(args, "codex_thread_id", "")
        task_id = str(getattr(args, "task_id", "")).strip()
        file_path = getattr(args, "file", "")
        timeout_seconds = getattr(
            args,
            "timeout",
            SYNCHRONOUS_SPEAK_TIMEOUT_SECONDS,
        )

        # Input parsing: process stdin envelope if requested

        if getattr(args, "stdin_json", False):
            request_envelope = json.loads(sys.stdin.read())
            text = str(request_envelope.get("text", ""))
            lang = str(request_envelope.get("lang", lang))
            emotion = str(request_envelope.get("emotion", emotion))
            codex_thread_id = str(
                request_envelope.get("codex_thread_id", codex_thread_id)
            )
            file_path = str(request_envelope.get("file", file_path))

        # Conditional check: evaluate domain preconditions and invariants

        if task_id:
            report_heading = f"Reporte de la tarea {task_id}"
            text = f"{report_heading}\n\n{text}" if text else report_heading

        embedded_file = _read_embedded_markdown(file_path) if file_path else None
        effective_timeout_seconds = _effective_synchronous_timeout_seconds(
            requested_timeout_seconds=timeout_seconds,
            text=text or "",
            embedded_file=embedded_file,
        )

        # Voice service dispatch: initialize synchronous VoiceService with timeout
        voice_service = VoiceService(
            synchronous=True,
            timeout_seconds=effective_timeout_seconds,
        )
        terminal_results: list[InstanceTerminalResult] = []

        # Content check: validate message text payload

        if not text and not embedded_file:

            # If no text or embedded file is provided, repeat the last dialogue
            log_step(args, "Attempting to repeat the last dialogue...")
            terminal_result = voice_service.speak(
                text="",
                lang=lang,
                emotion=emotion,
                codex_thread_id=codex_thread_id,
            )

            _append_terminal_result(terminal_results, terminal_result)

            repeat_result = terminal_results[0] if terminal_results else None
            repeat_output = (
                repeat_result.response

                # Conditional check: evaluate domain preconditions and invariants
                if repeat_result
                and repeat_result.state is InstanceTerminalState.RESPONSED
                else ""
            )
            args.json_payload = _build_public_payload(
                terminal_result=repeat_result,
                output=repeat_output,
            )

            return 0

        log_step(args, "Parsing speak inputs...")
        log_step(args, f"Synthesizing voice playback (lang={lang})...")

        # Content check: validate message text payload

        if text:
            terminal_result = voice_service.speak(
                text=text,
                lang=lang,
                emotion=emotion,
                codex_thread_id=codex_thread_id,
            )

            _append_terminal_result(terminal_results, terminal_result)

        # Conditional check: evaluate domain preconditions and invariants

        if embedded_file:
            escaped_file_name, embedded_markdown = embedded_file
            display_text = (
                f'<!-- avatar-file:start name="{escaped_file_name}" -->\n\n'
                f"## 📎 {escaped_file_name}\n\n{embedded_markdown}\n\n"
                "<!-- avatar-file:end -->"
            )

            request = AvatarSpeakRequest(
                text=clean_text_for_speech(display_text),
                display_text=display_text,
                lang=lang,
                emotion=emotion,
                codex_thread_id=codex_thread_id,
                has_embedded_file=True,
                manual_speech=True,
            )

            terminal_result = voice_service.present(request)

            _append_terminal_result(terminal_results, terminal_result)

        # Output mapping: format public JSON payload with state and output
        terminal_result = terminal_results[-1] if terminal_results else None
        response_text = ""

        # Iteration: loop over collection elements

        for terminal_result in terminal_results:

            # State guard: verify lifecycle status preconditions

            if terminal_result.state is not InstanceTerminalState.RESPONSED:
                continue

            response_text = terminal_result.response
            break

        args.json_payload = _build_public_payload(
            terminal_result=terminal_result,
            output=response_text,
        )

        return 0

    # Failure recovery: handle execution or transport exception

    except Exception as exc:
        error_message = f"__RED__Speech synthesis failed: {exc}__RESET__"
        print(render_placeholders(error_message, color_enabled), file=sys.stderr)

        return 1
