# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Asynchronous message-history persistence for voice requests.

Description: Asynchronous worker routines and persistence ports to decouple audio speech synthesis
             and avatar presentations from blocking message database updates.

File: core/brain/src/brain/infrastructure/voice/audio/voice_persistence.py
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Protocol

from brain.infrastructure.messages.models import MessageWriteDTO
from brain.infrastructure.messages.repository import MessageRepository, should_persist_message


class PersistenceRuntime(Protocol):
    """Narrow queue and error-reporting port required by persistence.

    Attributes:
        persistence_requests: Thread-safe queue containing pending message persistence DTO payloads.
        persistence_errors: In-memory sliding log recording unexpected persistence failures.
        lock: Reentrant lock synchronizing state access across daemon threads.
    """

    persistence_requests: queue.Queue[dict[str, str]]
    persistence_errors: list[dict[str, str]]
    lock: threading.RLock


def enqueue_message_persistence(memory: PersistenceRuntime, request: dict[str, str]) -> None:
    """Queue eligible history without delaying synthesis or playback.

    Args:
        memory: Shared persistence runtime providing request queue and error tracking capabilities.
        request: Dictionary containing voice presentation payload data and metadata attributes.
    """

    has_embedded_file = bool(request.get("hasEmbeddedFile")) or bool(request.get("has_embedded_file"))

    if has_embedded_file:
        return

    source_command = request.get("sourceCommand", "").casefold().strip()
    consumer_path = request.get("consumerPath", "").strip()

    if not consumer_path or not should_persist_message(source_command=source_command):
        return

    persisted_text = (
        request.get("text", "")
        if source_command
        else request.get("displayText", "") or request.get("text", "")
    )
    source_type = "operation" if source_command else "speak"

    payload: dict[str, str] = {
        "id": request["id"],
        "createdAt": request["createdAt"],
        "text": persisted_text,
        "emotion": request.get("emotion", ""),
        "chatId": request.get("codexThreadId", ""),
        "language": request.get("lang", "es"),
        "consumerPath": consumer_path,
        "sourceType": source_type,
        "sourceCommand": source_command,
        "sourcePhase": request.get("sourcePhase", ""),
    }

    memory.persistence_requests.put(payload)


def consume_persistence_requests(memory: PersistenceRuntime) -> None:
    """Persist queued jobs independently with bounded SQLite retries.

    Args:
        memory: Shared persistence runtime providing request queue, error tracking, and synchronization lock.
    """

    while True:

        request = memory.persistence_requests.get()

        try:

            message = MessageWriteDTO(
                id=request["id"],
                created_at=request["createdAt"],
                text=request["text"],
                emotion=request["emotion"],
                chat_id=request["chatId"],
                language=request["language"],
                source_type=request["sourceType"],
                source_command=request["sourceCommand"],
                source_phase=request["sourcePhase"],
            )

            last_error: Exception | None = None

            for attempt in range(3):

                try:

                    repository = MessageRepository(consumer_path=request["consumerPath"])
                    repository.append(message=message)
                    last_error = None

                    break

                except Exception as exc:

                    last_error = exc
                    retry_delay_seconds = 0.05 * (attempt + 1)
                    time.sleep(retry_delay_seconds)

            if last_error is not None:
                raise last_error

        except Exception as exc:

            with memory.lock:

                error_payload: dict[str, str] = {
                    "speakId": request.get("id", ""),
                    "consumerPath": request.get("consumerPath", ""),
                    "error": str(exc),
                }

                memory.persistence_errors.append(error_payload)
                del memory.persistence_errors[:-10]

        finally:

            memory.persistence_requests.task_done()