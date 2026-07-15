"""Action module to speak messages via Text-to-Speech."""

from __future__ import annotations

import argparse
import sys

from brain.infrastructure.voice import VoiceService
from brain.presentation.terminal import render_placeholders, log_step


def handle(args: argparse.Namespace) -> int:
    """Speak the parsed message text or repeat the last dialogue."""
    color_enabled = getattr(args, "color", False)
    try:
        text = args.text if args.text is not None else args.body
        lang = getattr(args, "lang", "es")
        emotion = getattr(args, "emotion", "")
        codex_thread_id = getattr(args, "codex_thread_id", "")
        voice_service = VoiceService()

        if not text:
            # If no text is provided, repeat the last dialogue
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
        voice_service.speak(text=text, lang=lang, emotion=emotion, codex_thread_id=codex_thread_id)
        args.json_payload = {
            "ok": True,
            "command": "speak",
            "operation": "enqueue",
            "language": lang,
            "emotion": emotion,
            "threadId": codex_thread_id,
            "characters": len(text),
        }

        return 0
    except Exception as exc:
        msg = f"__RED__Speech synthesis failed: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled), file=sys.stderr)
        return 1
