# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Best-effort dispatch for owner-reviewed CLI narration templates."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import re
import time
from datetime import datetime
from typing import Final

from brain.infrastructure.voice.contracts.avatar_speak_request import AvatarSpeakRequest
from brain.infrastructure.voice.service.voice_service import VoiceService
from brain.presentation.router.services.command_show_policy import CommandShowPolicy
from brain.presentation.router.services.narration_policy import (
    CommandNarration,
    build_narration_draft,
    render_without_refinement,
)


_CLOCK_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<!\d)(\d{1,2}):(\d{2})(?:\s*([ap])\.?\s*m\.?)?",
    re.IGNORECASE,
)
_DATE_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b")
_MONTHS: Final[tuple[str, ...]] = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
_RAPID_TASK_SIGNAL_KEY: Final[str] = "reviewed-template:add-task:output"


def _render_clock_token(match: re.Match[str]) -> str:
    """Render one matched clock token as a natural Spanish expression.

    Args:
        match: Matched clock expression.

    Returns:
        str: Spoken Spanish clock expression.
    """
    hour = int(match.group(1))
    minute = int(match.group(2))
    marker = (match.group(3) or "").lower()

    if marker == "p":
        hour = hour % 12 + 12
    elif marker == "a":
        hour %= 12

    if 6 <= hour < 12:
        period = "mañana"
    elif 12 <= hour < 20:
        period = "tarde"
    else:
        period = "noche"

    display_hour = hour % 12 or 12
    clock = f"{display_hour} en punto" if minute == 0 else f"{display_hour} y {minute}"

    return f"{clock} de la {period}"


def _render_date_token(match: re.Match[str]) -> str:
    """Render one matched numeric date as a natural Spanish expression.

    Args:
        match: Matched date expression.

    Returns:
        str: Spoken Spanish date expression, or the original token for an invalid month.
    """
    day, month, year = (int(part) for part in match.groups())

    if not 1 <= month <= len(_MONTHS):
        return match.group(0)

    return f"{day} de {_MONTHS[month - 1]} de {year}"


def natural_timestamp(value: str) -> str:
    """Render date and clock tokens as natural Spanish expressions.

    Args:
        value: Text containing numeric dates or clock values.

    Returns:
        Text with recognized timestamps rendered as spoken Spanish.
    """
    rendered_clock_values = _CLOCK_PATTERN.sub(_render_clock_token, value)

    return _DATE_PATTERN.sub(_render_date_token, rendered_clock_values)


def _escape_table_cell(value: object) -> str:
    """Format one table cell for safe Markdown rendering.

    Args:
        value: Source value supplied by a narration table row or column.

    Returns:
        str: Cell value with Markdown separators and line breaks escaped.
    """
    return str(value or "").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _select_visible_columns(rows: Sequence[Mapping[str, object]], columns: Sequence[str]) -> list[str]:
    """Return narration table columns after omitting a uniform source column.

    Args:
        rows: Table rows supplied by command arguments.
        columns: Candidate table columns supplied by command arguments.

    Returns:
        list[str]: Columns that should appear in the rendered table.
    """
    visible_columns = list(columns)

    has_uniform_source = len({str(row.get("source", "")) for row in rows}) <= 1
    if len(visible_columns) > 1 and "source" in visible_columns and has_uniform_source:
        visible_columns.remove("source")

    return visible_columns


def _render_narration_table(args: argparse.Namespace) -> str:
    """Render structured command rows for visual-only avatar presentation.

    Args:
        args: Parsed command arguments that may include narration table fields.

    Returns:
        str: Markdown table content, or an empty string when no table is configured.
    """
    rows = getattr(args, "narration_table_rows", None)
    columns = getattr(args, "narration_table_columns", None)

    if not rows or not columns:
        return ""

    visible_columns = _select_visible_columns(rows, columns)
    header = "| " + " | ".join(_escape_table_cell(column) for column in visible_columns) + " |"
    separator = "| " + " | ".join("---" for _ in visible_columns) + " |"
    body = [
        "| " + " | ".join(_escape_table_cell(row.get(column, "")) for column in visible_columns) + " |"
        for row in rows
    ]

    return "\n".join([header, separator, *body])


class VoiceSignalService:
    """Send reviewed command templates to the non-blocking voice daemon.

    Attributes:
        _rapid_task_window_seconds: Maximum interval that joins task announcements.
        _task_connectors: Rotating Spanish connectors for rapid task announcements.
    """

    _rapid_task_window_seconds = 12
    _task_connectors = ("Además, ", "También, ", "Y, además, ")

    @staticmethod
    def _build_presentation_options(show_policy: CommandShowPolicy | None) -> dict[str, object]:
        """Build the request presentation options from an optional display policy.

        Args:
            show_policy: Optional policy that controls voice request presentation.

        Returns:
            dict[str, object]: Options accepted by ``AvatarSpeakRequest``.
        """
        return {
            "show_message": getattr(show_policy, "show_message", True),
            "speak_message": getattr(show_policy, "speak_message", True),
            "hide_when_muted": getattr(show_policy, "hiden_on_muted", False),
            "message_level": getattr(show_policy, "level", "informative"),
            "pre_processor": getattr(show_policy, "pre_processor", "<default>"),
        }

    @staticmethod
    def _present(
        *,
        message: str,
        display_text: str,
        emotion: str,
        signal_key: str,
        source_command: str,
        source_phase: str,
        presentation_options: dict[str, object],
    ) -> None:
        """Submit one narration request to a fresh voice service instance.

        Args:
            message: Spoken narration text.
            display_text: Text shown in the avatar interface.
            emotion: Emotion selected for the avatar presentation.
            signal_key: Deduplication key for the narration signal.
            source_command: CLI command that produced the narration.
            source_phase: Command lifecycle phase that produced the narration.
            presentation_options: Display and speech options for the request.
        """
        request = AvatarSpeakRequest(
            text=message,
            display_text=display_text or message,
            lang="es",
            emotion=emotion,
            signal_key=signal_key,
            source_command=source_command,
            source_phase=source_phase,
            **presentation_options,
        )

        VoiceService().present(request)

    @staticmethod
    def emit(
        message: str,
        emotion: str = "happy",
        signal_key: str = "",
        display_text: str = "",
        source_command: str = "",
        source_phase: str = "",
        show_policy: CommandShowPolicy | None = None,
    ) -> None:
        """Dispatch one configured presentation and tolerate a cold-start race.

        Args:
            message: Spoken narration text.
            emotion: Default emotion unless the display policy overrides it.
            signal_key: Deduplication key for the narration signal.
            display_text: Text shown in the avatar interface.
            source_command: CLI command that produced the narration.
            source_phase: Command lifecycle phase that produced the narration.
            show_policy: Optional policy that controls voice request presentation.
        """
        presentation_options = VoiceSignalService._build_presentation_options(show_policy)
        animation = getattr(show_policy, "animation", "<default>")
        resolved_emotion = emotion if animation == "<default>" else animation

        try:
            VoiceSignalService._present(
                message=message,
                display_text=display_text,
                emotion=resolved_emotion,
                signal_key=signal_key,
                source_command=source_command,
                source_phase=source_phase,
                presentation_options=presentation_options,
            )
        except Exception:
            try:
                time.sleep(0.25)
                VoiceSignalService._present(
                    message=message,
                    display_text=display_text,
                    emotion=resolved_emotion,
                    signal_key=signal_key,
                    source_command=source_command,
                    source_phase=source_phase,
                    presentation_options=presentation_options,
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
        show_policy: CommandShowPolicy | None = None,
    ) -> None:
        """Emit an owner-reviewed template populated with command facts.

        Args:
            command: Canonical CLI command name.
            phase: Narration phase, normally ``call`` or ``output``.
            narration: Reviewed narration policy.
            args: Parsed command arguments.
            output: Serialized command output available to the template.
            succeeded: Whether command execution succeeded.
            cause: Failure explanation when command execution did not succeed.
            show_policy: Optional policy that controls voice request presentation.
        """
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
        table = _render_narration_table(args)

        if table:
            display_message = display_message + "\n" * 2 + table

        if command == "add-task" and phase == "output":
            display_message = self._connect_rapid_task(display_message)

            if not narration.refine_with_llm:
                message = display_message

        signal_key = f"reviewed-template:{command}:{phase}" if narration.refine_with_llm else ""

        self.emit(
            message,
            narration.emotion,
            signal_key=signal_key,
            display_text=display_message,
            source_command=command,
            source_phase=phase,
            show_policy=show_policy,
        )

    @staticmethod
    def sync_task_state(command: str, args: argparse.Namespace) -> None:
        """Reflect successful backlog transitions in avatar ambient state.

        Args:
            command: Successful backlog command name.
            args: Parsed command arguments containing status.
        """
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
        """Prefix task announcements that belong to one short CLI burst.

        Args:
            message: Newly rendered task announcement.

        Returns:
            str: Announcement with a rotating connector when appropriate.
        """
        try:
            speaks = VoiceService().snapshot().get("speaks", [])
            recent_count = 0
            now = datetime.now().astimezone()

            for speak in speaks:
                if speak.get("signalKey") != _RAPID_TASK_SIGNAL_KEY:
                    continue

                created_at = datetime.fromisoformat(str(speak.get("createdAt", "")))
                elapsed_seconds = (now - created_at).total_seconds()

                if elapsed_seconds <= cls._rapid_task_window_seconds:
                    recent_count += 1

            if recent_count:
                connector_index = (recent_count - 1) % len(cls._task_connectors)
                prefix = cls._task_connectors[connector_index]

                return prefix + message[:1].lower() + message[1:]
        except (OSError, TypeError, ValueError):
            pass

        return message
