"""Dispatch CLI speech requests and embedded Markdown presentations."""

# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import TypeAlias

from brain.infrastructure.voice import VoiceService
from brain.infrastructure.voice.contracts.avatar_speak_request import AvatarSpeakRequest
from brain.infrastructure.voice.service.voice_service import clean_text_for_speech
from brain.presentation.terminal import log_step, render_placeholders


EmbeddedMarkdown: TypeAlias = tuple[str, str]
"""Escaped filename and decoded UTF-8 Markdown content for avatar presentation."""


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

    if not path.is_file():
        raise ValueError(f"Embedded file is not a regular file: {file_path}")
    try:
        content = path.read_bytes()
        return html.escape(path.name, quote=True), content.decode("utf-8")
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

    try:
        text = args.text

        if text is None:
            text = args.body
        lang = getattr(args, "lang", "es")
        emotion = getattr(args, "emotion", "")
        codex_thread_id = getattr(args, "codex_thread_id", "")
        task_id = str(getattr(args, "task_id", "")).strip()
        file_path = getattr(args, "file", "")

        if getattr(args, "stdin_json", False):
            request_envelope = json.loads(sys.stdin.read())
            text = str(request_envelope.get("text", ""))
            lang = str(request_envelope.get("lang", lang))
            emotion = str(request_envelope.get("emotion", emotion))
            codex_thread_id = str(request_envelope.get("codex_thread_id", codex_thread_id))
            file_path = str(request_envelope.get("file", file_path))

        if task_id:
            report_heading = f"Reporte de la tarea {task_id}"
            text = f"{report_heading}\n\n{text}" if text else report_heading

        embedded_file = _read_embedded_markdown(file_path) if file_path else None
        voice_service = VoiceService()

        if not text and not embedded_file:
            # If no text or embedded file is provided, repeat the last dialogue
            log_step(args, "Attempting to repeat the last dialogue...")
            voice_service.speak(text="", lang=lang, emotion=emotion, codex_thread_id=codex_thread_id)
            args.json_payload = {
                "ok": True,
                "command": "speak",
                "operation": "repeat-last",
                "language": lang,
                "emotion": emotion,
                "threadId": codex_thread_id,
            }
            return 0

        log_step(args, f"Parsing speak inputs...")
        log_step(args, f"Synthesizing voice playback (lang={lang})...")

        if text:
            voice_service.speak(text=text, lang=lang, emotion=emotion, codex_thread_id=codex_thread_id)

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

            voice_service.present(request)

        args.json_payload = {
            "ok": True,
            "command": "speak",
            "operation": "enqueue",
            "language": lang,
            "emotion": emotion,
            "threadId": codex_thread_id,
            "characters": len(text or "") + (len(embedded_file[1]) if embedded_file else 0),
            "hasEmbeddedFile": embedded_file is not None,
        }

        return 0
    except Exception as exc:
        error_message = f"__RED__Speech synthesis failed: {exc}__RESET__"
        print(render_placeholders(error_message, color_enabled), file=sys.stderr)
        return 1
