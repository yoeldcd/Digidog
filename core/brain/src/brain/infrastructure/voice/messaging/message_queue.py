"""Manage the in-memory message FIFO and speak request lifecycle.

This module owns request enqueueing, replay selection, pending-request cleanup,
and retained speak-record state transitions for the voice runtime.
"""

# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

from __future__ import annotations

import queue
import threading
import time
import uuid
from datetime import datetime
from typing import Final, TypeAlias

from brain.infrastructure.voice.contracts.instance_results import InstanceTerminalState
from brain.infrastructure.voice.narration.markdown_narration import (
    normalize_avatar_message_text,
)

SpeakRequest: TypeAlias = dict[str, object]
"""Mutable internal payload for one queued or retained speak request."""

MAX_MEMORY_MESSAGES: Final[int] = 128
"""Maximum number of retained speak records kept in memory."""


class RequestQueue:
    """Track request work while keeping queue accounting behind a small API.

    The standard queue owns its task counter and exposes it only indirectly via
    ``task_done`` and ``join``.  This wrapper mirrors the counter for the
    daemon's non-blocking lifecycle checks without mutating ``queue.Queue``
    internals at call sites.
    """

    def __init__(self) -> None:
        """Initialize an unbounded request queue and its private work counter.

        Args:
            No arguments are accepted.

        Returns:
            None: The queue starts empty with no unfinished work.
        """
        self._queue: queue.Queue[SpeakRequest] = queue.Queue()
        self._condition = threading.Condition()
        self._work_count = 0

    def put(
        self,
        item: SpeakRequest,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:
        """Add one request and account for work until ``task_done``.

        Args:
            item: Request payload to append to the FIFO.
            block: Whether a bounded queue may wait for capacity.
            timeout: Maximum capacity wait in seconds.

        Returns:
            None: The request is accepted by the FIFO.
        """

        # Condition synchronization: acquire condition lock
        with self._condition:
            self._queue.put(item, block=block, timeout=timeout)
            self._work_count += 1
            self._condition.notify()

    def get_nowait(self) -> SpeakRequest:
        """Remove and return one queued request without waiting.

        Args:
            No arguments are accepted.

        Returns:
            SpeakRequest: The next FIFO request.
        """

        # Condition synchronization: acquire condition lock
        with self._condition:
            return self._queue.get_nowait()

    def get_next(self) -> SpeakRequest:
        """Wait for and return the next request in FIFO order.

        Args:
            No arguments are accepted.

        Returns:
            SpeakRequest: The next FIFO request.
        """

        return self.get()

    def get(
        self,
        block: bool = True,
        timeout: float | None = None,
    ) -> SpeakRequest:
        """Remove and return one request with standard queue wait semantics.

        Args:
            block: Whether to wait when the FIFO is empty.
            timeout: Maximum wait in seconds when ``block`` is true.

        Returns:
            SpeakRequest: The next FIFO request.

        Raises:
            queue.Empty: If no request arrives before a non-blocking or bounded
                wait expires.
            ValueError: If ``timeout`` is negative.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if not block:

            return self.get_nowait()

        # Timeout check: verify bounded wait duration
        if timeout is not None and timeout < 0:

            raise ValueError("Queue timeout must be non-negative.")

        deadline = None if timeout is None else time.monotonic() + timeout

        # Condition synchronization: acquire condition lock
        with self._condition:

            # Loop execution: process until boundary condition is satisfied
            while True:
                # Exception safety: execute operation within error boundary
                try:

                    return self._queue.get_nowait()

                # Failure recovery: handle execution or transport exception
                except queue.Empty:

                    # Conditional check: evaluate domain preconditions and invariants
                    if deadline is None:

                        self._condition.wait()
                        continue

                    remaining = deadline - time.monotonic()

                    # Conditional check: evaluate domain preconditions and invariants
                    if remaining <= 0:

                        raise

                    self._condition.wait(timeout=remaining)

    def task_done(self) -> None:
        """Mark one consumed request complete and update the private count.

        Args:
            No arguments are accepted.

        Returns:
            None: One accepted unit of work is marked complete.
        """

        # Condition synchronization: acquire condition lock
        with self._condition:

            self._queue.task_done()
            self._work_count -= 1

            # Conditional check: evaluate domain preconditions and invariants
            if self._work_count == 0:

                self._condition.notify_all()

    def qsize(self) -> int:
        """Return the approximate number of requests waiting in the FIFO.

        Args:
            No arguments are accepted.

        Returns:
            int: Approximate number of waiting requests.
        """

        # Condition synchronization: acquire condition lock
        with self._condition:

            return self._queue.qsize()

    def empty(self) -> bool:
        """Return whether the FIFO is currently empty.

        Args:
            No arguments are accepted.

        Returns:
            bool: Whether no request is currently waiting.
        """

        # Condition synchronization: acquire condition lock
        with self._condition:

            return self._queue.empty()

    def join(self) -> None:
        """Wait until every accepted request receives ``task_done``.

        Args:
            No arguments are accepted.

        Returns:
            None: All accepted work has completed.
        """

        # Condition synchronization: acquire condition lock
        with self._condition:

            # Loop execution: process until boundary condition is satisfied
            while self._work_count:
                self._condition.wait()

    def unfinished_work_count(self) -> int:
        """Return the number of queued or currently consumed requests.

        Args:
            No arguments are accepted.

        Returns:
            int: Number of requests awaiting ``task_done``.
        """

        # Condition synchronization: acquire condition lock
        with self._condition:

            return self._work_count

    def has_unfinished_work(self) -> bool:
        """Return whether queued or consumed request work remains outstanding.

        Args:
            No arguments are accepted.

        Returns:
            bool: Whether at least one request awaits ``task_done``.
        """

        # Condition synchronization: acquire condition lock
        with self._condition:

            return self._work_count > 0

    def remove_ids(self, ids: set[str]) -> int:
        """Remove matching queued IDs while preserving task accounting and FIFO.

        Args:
            ids: Exact request IDs that should be removed.

        Returns:
            int: Number of queued requests removed.

        The operation is intentionally encapsulated because a standard queue
        has no public arbitrary-removal operation.  It uses only the wrapped
        queue's public ``get_nowait``, ``task_done``, and ``put`` methods.
        """
        retained: list[SpeakRequest] = []
        removed_count = 0

        # Condition synchronization: acquire condition lock
        with self._condition:
            # Loop execution: process until boundary condition is satisfied
            while True:
                # Exception safety: execute operation within error boundary
                try:

                    item = self._queue.get_nowait()

                # Failure recovery: handle execution or transport exception
                except queue.Empty:

                    break

                self._queue.task_done()
                self._work_count -= 1

                # Conditional check: evaluate domain preconditions and invariants
                if str(item.get("id", "")) in ids:

                    removed_count += 1

                else:

                    retained.append(item)

            # Iteration: process sequence items
            for item in retained:
                self._queue.put(item)
                self._work_count += 1


            # Conditional check: evaluate domain preconditions and invariants
            if self._work_count == 0:

                self._condition.notify_all()

            # Conditional check: evaluate domain preconditions and invariants
            elif retained:

                self._condition.notify()


        return removed_count


def bounded_prelude_seconds(value: object) -> float:
    """Parse a bounded presentation lead-in from untrusted input.

    Args:
        value (object): Candidate HTTP value.

    Returns:
        float: Prelude duration clamped to zero through three seconds.
    """

    # Exception safety: execute operation within error boundary
    try:

        return max(0, min(3, float(value)))

    # Validation error handling: convert invalid input to domain exception
    except (TypeError, ValueError):

        return 0


class MessageQueueMixin:
    """Provide FIFO mutation and retained speak-record lifecycle operations.

    The host runtime supplies synchronization, queue, history, session, mute,
    and progressive-audio state used by these behavior-preserving methods.
    """

    def _put_request(self, request: SpeakRequest) -> None:
        """Publish one request and wake the single FIFO consumer.

        Args:
            request: Canonical request to append to the daemon FIFO.

        Returns:
            None: The request is published to the FIFO.
        """
        self.requests.put(request)

    def get_next_request(self) -> SpeakRequest:
        """Wait for and claim the next request using public queue operations.

        Args:
            No arguments are accepted.

        Returns:
            SpeakRequest: The next FIFO request whose task remains unfinished
            until the consumer calls ``task_done``.
        """

        return self.requests.get_next()

    def _drain_request_queue_locked(self, excluded_ids: set[str]) -> None:
        """Remove selected queued IDs while preserving all other FIFO items.

        Args:
            excluded_ids: Request IDs that must be removed from the queue.

        Returns:
            None: Matching queued requests are removed.

        The caller owns ``self.lock``.  The queue wrapper serializes this
        public-operation sequence with the FIFO consumer, so no queue
        implementation internals or task-counter mutations are required.
        """
        self.requests.remove_ids(excluded_ids)

    def _remove_queued_request_locked(self, speak_id: str) -> bool:
        """Remove one queued ID and restore every other item in FIFO order.

        Args:
            speak_id: Exact request identifier to remove.

        Returns:
            bool: Whether the target was present in the physical queue.
        """

        return self.requests.remove_ids({speak_id}) > 0

    def enqueue(
        self,
        text: str,
        lang: str,
        emotion: str = "",
        signal_key: str = "",
        prelude_seconds: float = 0,
        display_text: str = "",
        consumer_path: str = "",
        codex_thread_id: str = "",
        source_command: str = "",
        source_phase: str = "",
        keep_speaks_only: bool = False,
        clear_queue_before: bool = False,
        has_embedded_file: bool = False,
        manual_speech: bool = False,
        show_message: bool = True,
        speak_message: bool = True,
        hide_when_muted: bool = False,
        message_level: str = "informative",
        pre_processor: str = "<default>",
    ) -> str | None:
        """Queue a synthesis request and return its identifier.

        Args:
            text (str): Narration source text.
            lang (str): Narration language code.
            emotion (str): Avatar emotion for the request.
            signal_key (str): Optional refinement signal identity.
            prelude_seconds (float): Visual lead-in duration.
            display_text (str): Rich text shown by the avatar.
            consumer_path (str): Canonical message consumer path.
            codex_thread_id (str): Optional Codex reply target identifier.
            source_command (str): Command that produced the request.
            source_phase (str): Lifecycle phase that produced the request.
            has_embedded_file (bool): Whether the message contains an embedded file.
            manual_speech (bool): Whether narration requires an explicit user request.
            show_message (bool): Whether the avatar should display the message.
            speak_message (bool): Whether the voice service should synthesize speech.
            hide_when_muted (bool): Whether muted messages remain hidden.
            message_level (str): Avatar presentation severity or category.
            pre_processor (str): Preprocessing identity for the narration request.
            keep_speaks_only (bool): Whether command-produced records are deprecated.
            clear_queue_before (bool): Whether pending requests are cancelled first.

        Returns:
            str | None: New speak-job identifier, or ``None`` without text to
            replay.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:

            # Text normalization: format speech and display text
            normalized_text = normalize_avatar_message_text(text)
            display_source_text = display_text or normalized_text
            normalized_display_text = normalize_avatar_message_text(display_source_text)

            # Request composition: build canonical SpeakRequest payload
            request: SpeakRequest = {
                "text": normalized_text,
                "displayText": normalized_display_text,
                "lang": lang,
                "emotion": emotion,
                "signalKey": signal_key,
                "preludeSeconds": str(bounded_prelude_seconds(prelude_seconds)),
                "consumerPath": consumer_path,
                "codexThreadId": codex_thread_id,
                "sourceCommand": source_command,
                "sourcePhase": source_phase,
                "hasEmbeddedFile": has_embedded_file,
                "manualSpeech": manual_speech,
                "showMessage": show_message,
                "speakMessage": speak_message,
                "hideWhenMuted": hide_when_muted,
                "messageLevel": message_level,
                "preProcessor": pre_processor,
            }

            # Conditional check: evaluate domain preconditions and invariants
            if clear_queue_before:

                self.clear_pending_for_reaction()

            # Conditional check: evaluate domain preconditions and invariants
            if keep_speaks_only:
                # Iteration: process speak instances sequentially
                for queued in self.speaks:
                    is_queued = queued.get("status") == "QUEUED"
                    has_source_command = bool(queued.get("sourceCommand"))

                    # Conditional check: evaluate domain preconditions and invariants
                    if is_queued and has_source_command:
                        self._cancel_instance_locked(
                            str(queued["id"]), status="DEPRECATED"
                        )

            # Mute filtering: prune pending output-phase speaks in partial mute mode
            should_deprecate_partial_mute_speaks = (
                self.mute_mode == "partial" and not source_command
            )


            # Conditional check: evaluate domain preconditions and invariants
            if should_deprecate_partial_mute_speaks:
                # Iteration: process speak instances sequentially
                for queued in self.speaks:
                    is_queued = queued.get("status") == "QUEUED"
                    has_source_command = bool(queued.get("sourceCommand"))
                    is_output_phase = queued.get("sourcePhase") == "output"

                    # Conditional check: evaluate domain preconditions and invariants
                    if is_queued and has_source_command and is_output_phase:
                        self._cancel_instance_locked(
                            str(queued["id"]), status="DEPRECATED"
                        )


            # Content check: validate message text payload
            if normalized_text:

                self.last_request = request

            # Conditional check: evaluate domain preconditions and invariants
            elif self.last_request:

                request = dict(self.last_request)

                # Conditional check: evaluate domain preconditions and invariants
                if emotion:

                    request["emotion"] = emotion

            else:

                return None
            speak_id = f"speak-{uuid.uuid4().hex[:12]}"
            self.instance_lifecycle.register(speak_id)
            request.update(
                {
                    "id": speak_id,
                    "status": "QUEUED",
                    "createdAt": datetime.now().astimezone().isoformat(),
                }
            )
            self.speaks.insert(0, request)
            del self.speaks[MAX_MEMORY_MESSAGES:]
            self.last_activity = time.monotonic()
            self._put_request(request)


            return speak_id

    def clear_pending_for_reaction(self) -> int:
        """Atomically leave no pending message ahead of an idle reaction.

        History records remain terminally marked for diagnostics, while the
        physical FIFO is drained so its next item is exactly the reaction that
        ``enqueue`` appends after this method returns.

        Returns:
            int: Number of queued or working speak records cancelled.

        Args:
            No arguments are accepted.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:

            cleared_ids = {
                str(item.get("id", ""))

                # Iteration: process speak instances sequentially
                for item in self.speaks

                # State guard: verify lifecycle status preconditions
                if item.get("status") in {"QUEUED", "WORKING"}
                and item.get("id") != self.active_speak_id
            }

            # Queue drain: clear pending requests from FIFO queue
            self._drain_request_queue_locked(cleared_ids)


            # Iteration: process speak instances sequentially
            for speak_id in cleared_ids:

                # Processing tracking: remove speak ID from active processing set
                self.processing_speak_ids.discard(speak_id)
                self.processing_emotions.pop(speak_id, None)
                self.clear_progressive_audio(speak_id)
                self._cancel_instance_locked(speak_id)
            self._replay_pending = False


            return len(cleared_ids)

    def remove_queued_instance(self, speak_id: str) -> bool:
        """Remove one exact queued request while preserving FIFO accounting.

        Args:
            speak_id: Canonical queued ``speakId`` to remove.

        Returns:
            bool: Whether a matching queued request was removed.

        Raises:
            KeyError: If the lifecycle registry does not retain ``speak_id``.

        The single FIFO consumer remains the owner of its own ``get`` and
        ``task_done`` calls.  Temporary public-operation drains requeue every
        retained request, leaving queue accounting unchanged for those items.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:

            self.instance_lifecycle.result(speak_id)
            removed = self._remove_queued_request_locked(speak_id)


            # Conditional check: evaluate domain preconditions and invariants
            if not removed:

                return False

            self.processing_speak_ids.discard(speak_id)
            self.processing_emotions.pop(speak_id, None)
            self.clear_progressive_audio(speak_id)
            self._cancel_instance_locked(speak_id)
            self.last_activity = time.monotonic()


            return True


    def enqueue_active_file_narration(self) -> str | None:
        """Queue narration for the completed active embedded-file request.

        Args:
            No arguments are accepted.

        Returns:
            str | None: Requeued speak-job identifier, or ``None`` when no
                eligible active request exists.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:

            active = next(
                (
                    item

                    # Iteration: process speak instances sequentially
                    for item in self.speaks

                    # Identity check: verify instance ID invariants
                    if item.get("id") == self.active_speak_id
                    and item.get("hasEmbeddedFile")
                    and item.get("manualSpeech")
                    and item.get("status") not in {"QUEUED", "WORKING"}
                ),
                None,
            )

            # Conditional check: evaluate domain preconditions and invariants
            if active is None:

                return None
            active["status"] = "QUEUED"
            active["error"] = ""
            request = dict(active)
            request["manualSpeech"] = False
            request["internalReplay"] = True
            request["deprecated"] = "false"
            request["createdAt"] = datetime.now().astimezone().isoformat()
            self.last_activity = time.monotonic()
            self._put_request(request)


            return str(active["id"])


    def enqueue_replay(
        self, name: str | None = None, speak_id: str | None = None
    ) -> bool:
        """Queue replay of an existing identity without duplicating history.

        Replay is a logical FIFO turn, never a playback batch. The original
        speakId is preserved and persistence is skipped by ``internalReplay``.

        Args:
            name: Optional retained-message name used for selection.
            speak_id: Optional retained speak-job identifier used for selection.

        Returns:
            bool: ``True`` when one eligible replay request is queued.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:

            has_active_session = self.active_session is not None
            has_pending_replay = self._replay_pending
            has_unfinished_requests = self.requests.has_unfinished_work()


            # Conditional check: evaluate domain preconditions and invariants
            if has_active_session or has_pending_replay or has_unfinished_requests:

                return False

            # Message lookup: locate target message by name or speakId
            message = self.find_message(name=name) if name else None
            selected = (
                next((item for item in self.speaks if item.get("id") == speak_id), None)

                # Identity check: verify instance ID invariants
                if speak_id
                else None
            )

            # Conditional check: evaluate domain preconditions and invariants
            if selected is None and message is not None:

                selected = next(
                    (
                        item

                        # Iteration: process speak instances sequentially
                        for item in self.speaks

                        # Conditional check: evaluate domain preconditions and invariants
                        if item.get("id") == message.get("speakId")
                    ),
                    None,
                )

            # Replay selection: fallback to latest replayable message if unselected
            should_select_latest_replayable = (
                selected is None and not speak_id and not name
            )


            # Conditional check: evaluate domain preconditions and invariants
            if should_select_latest_replayable:
                selected = next(
                    (
                        item

                        # Iteration: process speak instances sequentially
                        for item in self.speaks

                        # State guard: verify lifecycle status preconditions
                        if item.get("status") not in {"DEPRECATED", "ERROR"}
                        and not self.is_muted(request=item)
                    ),
                    None,
                )

            selected_is_unreplayable = selected is None or selected.get("status") in {
                "DEPRECATED",
                "ERROR",
            }


            # Conditional check: evaluate domain preconditions and invariants
            if selected_is_unreplayable:

                return False


            # Conditional check: evaluate domain preconditions and invariants
            if message is None:

                message = next(
                    (
                        item

                        # Iteration: process sequence items
                        for item in self.messages

                        # Conditional check: evaluate domain preconditions and invariants
                        if item.get("speakId") == selected.get("id")
                    ),
                    None,
                )

            # Request composition: build internal replay payload with original ID
            request = dict(selected)
            request.update(
                {
                    "id": str(selected["id"]),
                    "sourceCommand": "",
                    "sourcePhase": "replay",
                    "manualSpeech": False,
                    "replayStatus": str(selected.get("status", "")),
                    "replayError": str(selected.get("error", "")),
                    "replayName": str(message.get("name", "")) if message else "",
                    "internalReplay": True,
                    "status": "QUEUED",
                    "error": "",
                    "deprecated": "false",
                    "createdAt": datetime.now().astimezone().isoformat(),
                }
            )
            selected["status"] = "QUEUED"
            selected["error"] = ""
            selected["deprecated"] = "false"
            self._replay_pending = True
            self.last_activity = time.monotonic()
            self._put_request(request)


            return True


    def begin_processing(self, speak_id: str, emotion: str = "") -> None:
        """Mark a synthesis job as actively processing.

        Args:
            speak_id (str): Speak-job identifier.
            emotion (str): Avatar emotion associated with the job.

        Returns:
            None: The job is marked as processing.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:

            # Processing tracking: add speak ID to active processing set
            self.processing_speak_ids.add(speak_id)
            self.processing_emotions[speak_id] = emotion
            self.last_activity = time.monotonic()


    def finish_processing(self, speak_id: str) -> None:
        """Clear a synthesis job without affecting concurrent work.

        Args:
            speak_id (str): Speak-job identifier to clear.

        Returns:
            None: The job is removed from processing state.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:

            self.processing_speak_ids.discard(speak_id)
            self.processing_emotions.pop(speak_id, None)


    def set_speak_status(
        self, speak_id: str, status: str, error: str = ""
    ) -> None:
        """Update a retained speak job's lifecycle status.

        Args:
            speak_id (str): Speak-job identifier.
            status (str): New lifecycle status.
            error (str): Optional failure detail.

        Returns:
            None: The retained lifecycle state is updated when still live.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:

            # Record lookup: find matching speak item in retained history
            speak = next(
                (item for item in self.speaks if item["id"] == speak_id),
                None,
            )

            # Conditional check: evaluate domain preconditions and invariants
            if speak is None:

                return

            # Exception safety: execute operation within error boundary
            try:
                current_terminal = self.instance_lifecycle.result(speak_id)

            # Key error handling: handle missing lookup entity
            except KeyError:

                return


            # Conditional check: evaluate domain preconditions and invariants
            if current_terminal is not None:

                return


            # State guard: verify lifecycle status preconditions
            if status == "DONE":
                result = self.instance_lifecycle.terminalize(
                    speak_id, InstanceTerminalState.SPEAKED
                )

                # Conditional check: evaluate domain preconditions and invariants
                if result is None:

                    return
                speak["status"] = status
                speak["error"] = error

                return


            # State guard: verify lifecycle status preconditions
            if status in {"CANCELLED", "DEPRECATED", "ERROR"}:
                result = self._cancel_instance_locked(
                    speak_id, status=status, error=error
                )

                # Conditional check: evaluate domain preconditions and invariants
                if result is None:

                    return

                # State guard: verify lifecycle status preconditions
                if status in {"CANCELLED", "DEPRECATED"}:

                    speak["deprecated"] = "true"


                return

            speak["status"] = status
            speak["error"] = error


    def update_speak_text(self, speak_id: str, text: str) -> None:
        """Replace retained visible text for a speak job.

        Args:
            speak_id (str): Speak-job identifier.
            text (str): Updated narration text.

        Returns:
            None: The retained text is updated when the job exists.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            speak = next(
                (item for item in self.speaks if item["id"] == speak_id),
                None,
            )


            # Conditional check: evaluate domain preconditions and invariants
            if speak:

                speak["text"] = text
