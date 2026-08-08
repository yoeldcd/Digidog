# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Projected-message and retained-history state for the Tk adapter."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from brain.presentation.avatar.interactivity.history_controller import (
    HistoryController, HistoryMessage, HistoryProjection,
)
from brain.presentation.avatar.interactivity.interaction_controller import ReplayTarget
from brain.presentation.avatar.interactivity.presentation_state import ProjectedMessageState
from brain.presentation.avatar.tk.runtime.backend import TkDaemonMessagesDTO


@dataclass(slots=True)
class TkMessageController:
    """Own Tk's current/last visual identity without owning queue policy.

    Attributes:
        current (HistoryMessage | None): Currently projected history message.
        last (HistoryMessage | None): Most recently rendered message.
        browsing_history (bool): Whether navigation is active.
        history_count (int): Number of retained messages.
        chronological_index (int): One-based current history position.
    """

    current: HistoryMessage | None = None
    last: HistoryMessage | None = None
    browsing_history: bool = False
    history_count: int = 0
    chronological_index: int = 0

    def apply(self, state: ProjectedMessageState, render: Callable[[str, str], None]) -> None:
        """Project daemon text while retaining terminal identity for REPLAY.

        Args:
            state (ProjectedMessageState): Daemon state projected into the Tk window.
            render (Callable[[str, str], None]): Callback that renders normalized text and emotion.

        Returns:
            None.
        """
        self.history_count = max(self.history_count, state.history_count)

        if state.active_speak_id:
            self.chronological_index = max(1, state.history_count)

        if state.display_text:
            message = HistoryMessage(
                speak_id=state.active_speak_id,
                display_text=state.display_text,
                emotion=state.emotion,
                consumer_path=state.consumer_path,
                codex_thread_id=state.codex_thread_id,
                has_embedded_file=state.has_embedded_file,
                manual_speech=state.manual_speech,
            )
            self.current = self.last = message
            self.browsing_history = False
            render(message.display_text, message.emotion)
            return

        render("", "")

    def replay_target(self) -> ReplayTarget:
        """Return the stable terminal identity used by replay actions.

        Returns:
            ReplayTarget: Replay target for the current or last rendered message.
        """
        message = self.current or self.last

        if message is None:
            return ReplayTarget()

        return ReplayTarget(
            speak_id=message.speak_id,
            audio_name=message.audio_name,
            has_embedded_file=message.has_embedded_file,
            manual_speech=message.manual_speech,
            browsing_history=self.browsing_history,
        )

    def retained_history(self, payload: TkDaemonMessagesDTO | Mapping[str, Any]) -> HistoryController:
        """Normalize daemon history into the shared chronological controller.

        Args:
            payload (TkDaemonMessagesDTO | Mapping[str, Any]): Typed history payload containing ``speaks`` and ``messages`` arrays.

        Returns:
            HistoryController: Shared history controller with resolved audio names.
        """
        audio = {
            str(item.get("speakId", "")): str(item.get("name", ""))
            for item in payload.get("messages", [])
            if isinstance(item, Mapping) and item.get("speakId")
        }

        items: list[dict[str, Any]] = []
        for raw in payload.get("speaks", []):
            if not isinstance(raw, Mapping):
                continue
            item = dict(raw)
            item["audioName"] = audio.get(str(item.get("id", "")), "")
            items.append(item)

        return HistoryController.from_mappings(items)

    def select(self, projection: HistoryProjection, render: Callable[[str, str], None]) -> None:
        """Render a selected history projection and update navigation state.

        Args:
            projection (HistoryProjection): Shared history selection result.
            render (Callable[[str, str], None]): Callback receiving display text and emotion.

        Returns:
            None.
        """
        self.current = projection.message
        self.browsing_history = projection.browsing_history
        self.history_count = projection.total
        self.chronological_index = projection.chronological_index
        render(projection.message.display_text, projection.message.emotion)