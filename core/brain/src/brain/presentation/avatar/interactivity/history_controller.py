# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Newest-first avatar history with chronological user-facing numbering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, TypedDict


class HistoryMessagePayload(TypedDict, total=False):
    """Wire fields accepted from one retained daemon history record.

    Attributes:
        id (str): Stable speech identifier.
        displayText (str): Display-ready message text.
        text (str): Legacy text field used when displayText is absent.
        emotion (str): Message emotion name.
        consumerPath (str): Consumer that produced the message.
        codexThreadId (str): Associated Codex conversation identifier.
        audioName (str): Optional generated audio asset name.
        hasEmbeddedFile (bool): Whether the message contains a file block.
        manualSpeech (bool): Whether speech was requested manually.
    """

    id: str
    displayText: str
    text: str
    emotion: str
    consumerPath: str
    codexThreadId: str
    audioName: str
    hasEmbeddedFile: bool
    manualSpeech: bool


@dataclass(frozen=True, slots=True)
class HistoryMessage:
    """Toolkit-neutral retained message projection.

    Attributes:
        speak_id (str): Stable speech identifier.
        display_text (str): Text shown in the message bubble.
        emotion (str): Message emotion name.
        consumer_path (str): Consumer that produced the message.
        codex_thread_id (str): Associated Codex conversation identifier.
        audio_name (str): Optional generated audio asset name.
        has_embedded_file (bool): Whether the message contains a file block.
        manual_speech (bool): Whether speech was requested manually.
    """

    speak_id: str
    display_text: str
    emotion: str = ""
    consumer_path: str = ""
    codex_thread_id: str = ""
    audio_name: str = ""
    has_embedded_file: bool = False
    manual_speech: bool = False

    @classmethod
    def from_mapping(cls, item: HistoryMessagePayload) -> "HistoryMessage":
        """Normalize one daemon history mapping.

        Args:
            item (HistoryMessagePayload): Raw retained message record.

        Returns:
            HistoryMessage: Toolkit-neutral retained message projection.
        """
        return cls(
            speak_id=str(item.get("id", "")),
            display_text=str(item.get("displayText") or item.get("text", "")),
            emotion=str(item.get("emotion", "")),
            consumer_path=str(item.get("consumerPath", "")),
            codex_thread_id=str(item.get("codexThreadId", "")),
            audio_name=str(item.get("audioName", "")),
            has_embedded_file=bool(item.get("hasEmbeddedFile", False)),
            manual_speech=bool(item.get("manualSpeech", False)),
        )


@dataclass(frozen=True, slots=True)
class HistoryProjection:
    """Selected message and its chronological N/N coordinates.

    Attributes:
        message (HistoryMessage): Selected retained message.
        storage_index (int): Newest-first storage position.
        chronological_index (int): User-facing one-based position.
        total (int): Number of retained messages.
    """

    message: HistoryMessage
    storage_index: int
    chronological_index: int
    total: int

    @property
    def browsing_history(self) -> bool:
        """Whether selection is older than the newest retained message.

        Returns:
            bool: True when the selection is not the newest message.
        """
        return self.storage_index > 0


class HistoryController:
    """Navigate newest-first storage without leaking ordering rules to widgets.

    Attributes:
        _messages (tuple[HistoryMessage, ...]): Non-empty retained projections.
    """

    def __init__(self, messages: Iterable[HistoryMessage]) -> None:
        """Initialize a controller with displayable messages in newest-first order.

        Args:
            messages (Iterable[HistoryMessage]): Retained message projections.

        Returns:
            None: The immutable navigation sequence is ready.
        """
        self._messages = tuple(message for message in messages if message.display_text)

    @classmethod
    def from_mappings(cls, items: Iterable[HistoryMessagePayload]) -> "HistoryController":
        """Build history from daemon mappings already ordered newest first.

        Args:
            items (Iterable[HistoryMessagePayload]): Raw retained records.

        Returns:
            HistoryController: Controller over normalized history messages.
        """
        parsed_messages: list[HistoryMessage] = [
            HistoryMessage.from_mapping(item) for item in items
        ]
        return cls(parsed_messages)

    @property
    def messages(self) -> tuple[HistoryMessage, ...]:
        """Return the retained history message projections.

        Returns:
            tuple[HistoryMessage, ...]: Retained messages in newest-first order.
        """
        return self._messages

    @property
    def total(self) -> int:
        """Return the number of retained display messages.

        Returns:
            int: Number of messages available for navigation.
        """
        return len(self._messages)

    def newest(self) -> HistoryProjection | None:
        """Project the newest item as N/N.

        Returns:
            HistoryProjection | None: Newest projection, or None when empty.
        """
        return self._projection(0) if self._messages else None

    def select(self, speak_id: str) -> HistoryProjection | None:
        """Project a retained message by stable speak identity.

        Args:
            speak_id (str): Stable speech identifier to select.

        Returns:
            HistoryProjection | None: Matching projection, or None when absent.
        """
        index = next(
            (position for position, item in enumerate(self._messages) if item.speak_id == speak_id),
            None,
        )

        return self._projection(index) if index is not None else None

    def navigate(self, speak_id: str, direction: int) -> HistoryProjection | None:
        """Move older for negative direction and newer for positive direction.

        Args:
            speak_id (str): Current selected speech identifier.
            direction (int): Negative for older, positive for newer.

        Returns:
            HistoryProjection | None: Bounded destination projection, or None when empty.
        """
        if not self._messages:
            return None

        current = self.select(speak_id) or self.newest()
        assert current is not None

        delta = 1 if direction < 0 else -1
        target = max(0, min(current.storage_index + delta, self.total - 1))
        return self._projection(target)

    def _projection(self, storage_index: int) -> HistoryProjection:
        """Build chronological coordinates for one storage position.

        Args:
            storage_index (int): Newest-first position to project.

        Returns:
            HistoryProjection: Selected message and its N/N coordinates.
        """
        return HistoryProjection(
            message=self._messages[storage_index],
            storage_index=storage_index,
            chronological_index=self.total - storage_index,
            total=self.total,
        )
