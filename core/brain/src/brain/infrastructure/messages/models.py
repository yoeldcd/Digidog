# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Typed contracts for persisted avatar messages."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class MessageWriteDTO:
    """Validated message accepted by a workspace message repository.

    Attributes:
        id (str): Immutable message identifier.
        created_at (str): Canonical creation timestamp.
        text (str): Persisted message body.
        emotion (str): Optional avatar emotion.
        chat_id (str): Optional source chat identifier.
        language (str): Message language code.
        source_type (str): Originating message operation type.
        source_command (str): Originating CLI command.
        source_phase (str): Originating command lifecycle phase.
    """

    id: str
    created_at: str
    text: str
    emotion: str = ""
    chat_id: str = ""
    language: str = "es"
    source_type: str = "speak"
    source_command: str = ""
    source_phase: str = ""


@dataclass(frozen=True, slots=True)
class MessageRecordDTO(MessageWriteDTO):
    """Persisted message projection returned to CLI, Explorer, and search."""

    def as_mapping(self) -> dict[str, str]:
        """Return a JSON-safe mapping with explicit date and time projections.

        Returns:
            dict[str, str]: Message fields plus derived date and time values.
        """
        payload: dict[str, str] = asdict(self)
        timestamp: datetime = datetime.fromisoformat(self.created_at)
        payload["date"] = timestamp.date().isoformat()
        payload["time"] = timestamp.timetz().isoformat(timespec="seconds")
        return payload
