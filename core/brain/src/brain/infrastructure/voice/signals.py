# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Best-effort dispatch for owner-reviewed CLI narration templates."""

from __future__ import annotations

import argparse
import re
import time
from datetime import datetime

from brain.infrastructure.voice.service import VoiceService
from brain.presentation.router.services.narration_policy import (
    CommandNarration,
    build_narration_draft,
    render_without_refinement,
)


def natural_timestamp(value: str) -> str:
    """Render date and clock tokens as natural Spanish expressions."""
    pattern = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?:\s*([ap])\.?\s*m\.?)?", re.IGNORECASE)

    def replace(match: re.Match[str]) -> str:
        hour = int(match.group(1))
        minute = int(match.group(2))
        marker = (match.group(3) or "").lower()
        if marker == "p":
            hour = hour % 12 + 12
        elif marker == "a":
            hour %= 12
        period = "mañana" if 6 <= hour < 12 else "tarde" if 12 <= hour < 20 else "noche"
        display_hour = hour % 12 or 12
        clock = f"{display_hour} en punto" if minute == 0 else f"{display_hour} y {minute}"
        return f"{clock} de la {period}"

    rendered = pattern.sub(replace, value)
    months = (
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    )

    def replace_date(match: re.Match[str]) -> str:
        day, month, year = (int(part) for part in match.groups())
        if not 1 <= month <= 12:
            return match.group(0)
        return f"{day} de {months[month - 1]} de {year}"

    return re.sub(r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b", replace_date, rendered)


class VoiceSignalService:
    """Send reviewed command templates to the non-blocking voice daemon."""

    _rapid_task_window_seconds = 12
    _task_connectors = ("Además, ", "También, ", "Y, además, ")

    @staticmethod
    def emit(message: str, emotion: str = "happy", signal_key: str = "", display_text: str = "") -> None:
        """Dispatch speech best-effort and tolerate one cold-start race."""
        try:
            VoiceService().present(
                text=message, display_text=display_text or message,
                lang="es", emotion=emotion, signal_key=signal_key,
            )
        except Exception:
            try:
                time.sleep(.25)
                VoiceService().present(
                    text=message, display_text=display_text or message,
                    lang="es", emotion=emotion, signal_key=signal_key,
                )
            except Exception:
                pass

    def emit_reviewed(
        self,
        *,
        command: str,
        phase: str,
        narration: CommandNarration,
        args: argparse.Namespace,
        output: str = "",
        succeeded: bool = True,
        cause: str = "",
    ) -> None:
        """Emit one owner-reviewed template with real parser and command facts."""
        template = narration.call_template if phase == "call" else narration.output_template
        draft = build_narration_draft(
            command=command,
            template=template,
            args=args,
            output=output,
            succeeded=succeeded,
            phase=phase,
            cause=cause,
        )
        display_message = render_without_refinement(draft)
        message = draft if narration.refine_with_llm else display_message
        if command == "add-task" and phase == "output":
            display_message = self._connect_rapid_task(display_message)
            if not narration.refine_with_llm:
                message = display_message
        signal_key = f"reviewed-template:{command}:{phase}" if narration.refine_with_llm else ""
        self.emit(message, narration.emotion, signal_key=signal_key, display_text=display_message)

    @staticmethod
    def sync_task_state(command: str, args: argparse.Namespace) -> None:
        """Reflect successful backlog transitions in the avatar's ambient state."""
        ambient_state = ""
        if command == "set-task-status":
            status = str(getattr(args, "status", "")).strip().upper()
            if status == "WORKING":
                ambient_state = "working"
            elif status == "DONE":
                ambient_state = "awaiting"
        elif command in {"task-finished", "complete-work"}:
            ambient_state = "awaiting"
        if not ambient_state:
            return
        try:
            VoiceService().set_ambient_state(ambient_state)
        except Exception:
            pass

    @classmethod
    def _connect_rapid_task(cls, message: str) -> str:
        """Prefix task announcements that belong to one short CLI burst."""
        try:
            speaks = VoiceService().snapshot().get("speaks", [])
            recent_count = 0
            now = datetime.now().astimezone()
            for speak in speaks:
                if speak.get("signalKey") != "reviewed-template:add-task:output":
                    continue
                created_at = datetime.fromisoformat(str(speak.get("createdAt", "")))
                if (now - created_at).total_seconds() <= cls._rapid_task_window_seconds:
                    recent_count += 1
            if recent_count:
                prefix = cls._task_connectors[(recent_count - 1) % len(cls._task_connectors)]
                return prefix + message[:1].lower() + message[1:]
        except (OSError, TypeError, ValueError):
            pass
        return message
