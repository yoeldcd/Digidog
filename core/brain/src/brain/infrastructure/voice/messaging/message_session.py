# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Active-message sessions, Qt leases, terminal STOP, and lifecycle ownership."""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from brain.infrastructure.avatar.process.avatar_process import AvatarProcessSupervisor
from brain.infrastructure.voice.audio.engines import PlaybackProcess
from brain.infrastructure.voice.contracts.instance_results import (
    InstanceTerminalResult,
    InstanceTerminalState,
)
from brain.infrastructure.voice.daemon.runtime_state import IDLE_TTL_SECONDS
from brain.infrastructure.voice.messaging.message_queue import SpeakRequest


@dataclass(slots=True)
class TtsBatchSession:
    """Own the private synthesis and playback pipeline for one logical message.

    Batches never enter the daemon message FIFO, history, persistence, queue
    depth, or GUI contract. STOP invalidates the producer generation before
    draining buffers and terminating the player, preventing late synthesis.

    Attributes:
        speak_id: Stable identifier of the logical message that owns this pipeline.
        generation: Current producer generation accepted by the session.
        batches: Internal FIFO of synthesized playback batches.
        cancelled: Signal that rejects late producers and playback registrations.
        producer_done: Signal that no further batch production is expected.
        finished: Signal that cancellation completed its terminal cleanup.
        player: Currently registered playback process, when one is active.
        lock: Re-entrant lock protecting session state and player registration.
    """

    speak_id: str
    generation: int
    batches: queue.Queue[dict[str, object]] = field(default_factory=queue.Queue)
    cancelled: threading.Event = field(default_factory=threading.Event)
    producer_done: threading.Event = field(default_factory=threading.Event)
    finished: threading.Event = field(default_factory=threading.Event)
    player: PlaybackProcess | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)

    def accepts(self, generation: int) -> bool:
        """Return whether work belongs to the still-live generation.

        Args:
            generation: Producer generation that requests publication access.

        Returns:
            Whether the generation remains current and the session is not cancelled.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            return not self.cancelled.is_set() and generation == self.generation

    def publish(self, batch: dict[str, object], generation: int) -> bool:
        """Publish one internal batch only if its generation is still live.

        Args:
            batch: Private playback payload produced for the owning message.
            generation: Producer generation that owns the batch.

        Returns:
            Whether the session accepted the batch into its private FIFO.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:

            # Conditional check: evaluate domain preconditions and invariants
            if self.cancelled.is_set() or generation != self.generation:

                return False

            self.batches.put(batch)

            return True

    def register_player(self, player: PlaybackProcess, generation: int) -> bool:
        """Atomically expose a player or terminate it after concurrent STOP.

        Args:
            player: Started process that may be terminated if STOP already won.
            generation: Producer generation that owns the started process.

        Returns:
            Whether the player was registered as the active process.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:

            # Conditional check: evaluate domain preconditions and invariants
            if self.cancelled.is_set() or generation != self.generation:

                player.terminate()

                return False

            self.player = player

            return True

    def release_player(self, player: PlaybackProcess) -> None:
        """Forget a completed player without clearing a newer registration.

        Args:
            player: Completed playback process requesting release from the session.

        Returns:
            None: The active registration is cleared only when it matches ``player``.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:

            # Conditional check: evaluate domain preconditions and invariants
            if self.player is player:

                self.player = None

    def cancel(self) -> None:
        """Invalidate work, terminate playback, and release batch waiters.

        Args:
            No arguments are accepted.

        Returns:
            None: Session cancellation completes synchronously.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:

            self.cancelled.set()
            self.generation += 1

            # Conditional check: evaluate domain preconditions and invariants
            if self.player is not None:

                self.player.terminate()
                self.player = None

            # Loop execution: process until boundary condition is satisfied
            while True:

                # Exception safety: execute operation within error boundary
                try:

                    self.batches.get_nowait()

                # Failure recovery: handle execution or transport exception
                except queue.Empty:

                    break

                else:

                    self.batches.task_done()

            self.finished.set()


@dataclass(frozen=True, slots=True)
class WindowReadyLease:
    """Represent the immutable identity of one acknowledged Qt process generation.

    Attributes:
        pid: Process identifier acknowledged by the Qt window, when available.
        generation: Window spawn generation that owns the acknowledgement.
    """

    pid: int | None
    generation: int


@dataclass(slots=True)
class ActiveMessageSession:
    """Own one logical message's identity, visual state, mute, and TTS lifecycle.

    The GUI projects this session and sends control events. Only audible
    sessions receive a private TTS batch pipeline.

    Attributes:
        request: Original daemon request that defines message identity and display data.
        generation: Monotonic session generation used to reject stale asynchronous work.
        muted: Whether this session suppresses audible playback.
        cancelled: Signal that invalidates the active presentation and TTS generation.
        presentation_done: Signal that the visual lifecycle reached a terminal state.
        tts: Private TTS batch pipeline for audible sessions, when applicable.
        window_lease: Validated Qt window lease that owns this projection, when required.
        composer_hold_open: Whether the exact message has an open composer hold.
        composer_hold_released: Event released when the composer hold resolves.
        natural_close_started: Whether natural completion claimed the close boundary.
    """

    request: SpeakRequest
    generation: int
    muted: bool
    cancelled: threading.Event = field(default_factory=threading.Event)
    presentation_done: threading.Event = field(default_factory=threading.Event)
    tts: TtsBatchSession | None = None
    window_lease: WindowReadyLease | None = None
    composer_hold_open: bool = False
    composer_hold_released: threading.Event = field(default_factory=threading.Event)
    natural_close_started: bool = False

    @property
    def speak_id(self) -> str:
        """Return the stable logical message identifier.

        Args:
            No arguments are accepted.

        Returns:
            Stable speak identifier extracted from the original request.
        """

        return str(self.request["id"])

    def cancel(self) -> None:
        """Terminally cancel presentation and every private TTS batch.

        Args:
            No arguments are accepted.

        Returns:
            None: Presentation and private playback cancellation complete synchronously.
        """
        self.cancelled.set()
        self.presentation_done.set()
        self.composer_hold_open = False
        self.composer_hold_released.set()

        # Conditional check: evaluate domain preconditions and invariants
        if self.tts is not None:
            self.tts.cancel()

    def release_composer_hold(self) -> None:
        """Release a composer hold and wake its exact waiting session.

        Args:
            No arguments are accepted.

        Returns:
            None: The hold is marked closed and its natural-close waiter wakes.
        """

        self.composer_hold_open = False
        self.composer_hold_released.set()

    def open_composer_hold(self) -> bool:
        """Open the composer hold for this exact active message once.

        Args:
            No arguments are accepted.

        Returns:
            bool: Whether this call acquired the previously closed hold.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if self.cancelled.is_set() or self.composer_hold_open:
            return False

        self.composer_hold_open = True
        self.composer_hold_released.clear()

        return True


class MessageSessionMixin:
    """Coordinate Qt leases, one active message session, STOP, and playback.

    The composing runtime supplies the synchronized state consumed by these
    methods. Every lifecycle transition remains under its shared re-entrant
    lock so concurrent producers, window supervision, and STOP cannot publish
    stale work.
    """

    def bind_window_supervisor(self, supervisor: AvatarProcessSupervisor) -> None:
        """Bind readiness validation to the real child-process supervisor.

        Args:
            supervisor: Supervisor owning the current avatar process.

        Returns:
            None: The supervisor becomes the source for future readiness checks.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            self.window_supervisor = supervisor

    def register_window_process(self, pid: int) -> None:
        """Publish the only child PID eligible to acknowledge this generation.

        Args:
            pid: Process identifier for the spawned avatar window.

        Returns:
            None: The PID is recorded as the current window process lease.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            process_id = int(pid)
            self.current_window_pid = process_id
            self.window_pids = [process_id]

    def mark_window_ready(self, pid: int | None = None) -> bool:
        """Accept readiness only from the supervisor's current live child PID.

        Args:
            pid: Process identifier reported by the ready window, when available.

        Returns:
            Whether the readiness signal belongs to the current process lease.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            supervisor = self.window_supervisor
            live_pid = (
                supervisor.pid if supervisor is not None else self.current_window_pid
            )

            # Conditional check: evaluate domain preconditions and invariants
            if supervisor is not None:
                # Conditional check: evaluate domain preconditions and invariants
                if pid is None or pid != live_pid or pid != self.current_window_pid:
                    return False

            # Conditional check: evaluate domain preconditions and invariants
            elif self.current_window_pid is not None and pid != self.current_window_pid:
                return False

            self.last_activity = time.monotonic()
            self.ready_window_pid = pid
            self.window_ready.set()

            return True

    def prepare_for_window_spawn(self) -> int:
        """Invalidate the prior PID lease and open a fresh spawn generation.

        Args:
            No arguments are accepted.

        Returns:
            int: The new window spawn generation.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            self.window_generation += 1
            self.ready_window_pid = None
            self.current_window_pid = None
            self.window_pids = []
            self.window_ready.clear()
            self.window_wait_cancelled.clear()

            return self.window_generation

    def window_lease_is_current(self, lease: WindowReadyLease | None) -> bool:
        """Validate generation and PID against the supervisor's live process.

        Args:
            lease: Window lease whose generation and process identity are checked.

        Returns:
            bool: Whether the lease still belongs to the current live window.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if lease is None:
            return self.window_supervisor is None

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            window_is_ready = self.window_ready.is_set()
            generation_is_current = lease.generation == self.window_generation
            pid_is_current = lease.pid == self.ready_window_pid

            # Conditional check: evaluate domain preconditions and invariants
            if not window_is_ready:
                return False

            # Conditional check: evaluate domain preconditions and invariants
            if not generation_is_current:
                return False

            # Conditional check: evaluate domain preconditions and invariants
            if not pid_is_current:
                return False

            # Conditional check: evaluate domain preconditions and invariants
            if self.window_supervisor is None:
                return (
                    self.current_window_pid is None
                    or lease.pid == self.current_window_pid
                )

            return lease.pid == self.current_window_pid == self.window_supervisor.pid

    def wait_for_window(self, request: SpeakRequest) -> WindowReadyLease | None:
        """Acquire an interruptible, PID-bound lease before message projection.

        Args:
            request: FIFO request whose speak identifier waits for a live window.

        Returns:
            Current Qt window lease, or ``None`` when waiting is terminally cancelled.
        """
        speak_id = str(request["id"])
        is_internal_replay = bool(request.get("internalReplay"))

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            self.awaiting_window_speak_id = speak_id
            self.window_wait_cancelled.clear()

        # Loop execution: process until boundary condition is satisfied
        while True:
            # Timeout check: verify bounded wait duration
            if self.window_ready.wait(timeout=0.025):
                # Concurrency control: acquire lock for thread-safe state mutation
                with self.lock:
                    lease = WindowReadyLease(
                        self.ready_window_pid, self.window_generation
                    )

                # Conditional check: evaluate domain preconditions and invariants
                if self.window_lease_is_current(lease):
                    return lease

                # Concurrency control: acquire lock for thread-safe state mutation
                with self.lock:
                    # Conditional check: evaluate domain preconditions and invariants
                    if (
                        self.ready_window_pid == lease.pid
                        and self.window_generation == lease.generation
                    ):
                        self.ready_window_pid = None
                        self.window_ready.clear()

            # Concurrency control: acquire lock for thread-safe state mutation
            with self.lock:
                terminal_before_window = (
                    self.is_speak_terminal(speak_id) and not is_internal_replay
                )

                # Conditional check: evaluate domain preconditions and invariants
                if (
                    self.stop_requested
                    or self.window_wait_cancelled.is_set()
                    or terminal_before_window
                ):
                    # Identity check: verify instance ID invariants
                    if self.awaiting_window_speak_id == speak_id:
                        self.awaiting_window_speak_id = ""

                    return None

    def record_supervision_error(self, error: Exception) -> None:
        """Retain a bounded diagnostic trail without killing supervision.

        Args:
            error: Supervision failure to retain in the bounded diagnostic trail.

        Returns:
            None: The error is appended and older entries beyond the bound are dropped.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            self.supervision_errors.append(str(error))
            del self.supervision_errors[:-10]

    def request_daemon_stop(self) -> None:
        """Terminally cancel active/waiting work and release readiness waits.

        Args:
            No arguments are accepted.

        Returns:
            None: Stop state and cancellation signals are applied synchronously.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            self.stop_requested = True
            self.window_wait_cancelled.set()
            self.stop_active_speak()
            self.cancel_all_instances()

    def cancel_instance(self, instance_id: str) -> InstanceTerminalResult | None:
        """Cancel one exact instance without advancing another FIFO item.

        Args:
            instance_id: Exact canonical ``speakId`` to cancel.

        Returns:
            InstanceTerminalResult | None: The cancellation result when this
            call wins, or ``None`` for a stale terminal transition.

        Raises:
            KeyError: If the instance is unknown or no longer retained.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            current_result = self.instance_lifecycle.result(instance_id)

            # Conditional check: evaluate domain preconditions and invariants
            if current_result is not None:
                return None

            active_session = self.active_session
            active_ids = {
                self.active_speak_id,
                self.awaiting_window_speak_id,
                *(self.processing_speak_ids),
            }

            active_session_matches = (
                active_session is not None and active_session.speak_id == instance_id
            )
            active_instance_requested = (
                active_session_matches or instance_id in active_ids
            )

            # Conditional check: evaluate domain preconditions and invariants
            if active_instance_requested:

                self.stop_active_speak()

                return self._canceled_instance_result(instance_id)

            # Identity check: verify instance ID invariants
            if self.remove_queued_instance(instance_id):

                return self._canceled_instance_result(instance_id)

            return self._cancel_instance_locked(instance_id)

    def _canceled_instance_result(
        self, instance_id: str
    ) -> InstanceTerminalResult | None:
        """Return the exact cancellation result when this transition won.

        Args:
            instance_id: Exact canonical ``speakId`` whose result is inspected.

        Returns:
            InstanceTerminalResult | None: The cancellation result when this
            transition won, or ``None`` for a stale terminal transition.
        """

        result = self.instance_lifecycle.result(instance_id)

        # State guard: verify lifecycle status preconditions
        if result is None or result.state is not InstanceTerminalState.CANCELED:

            return None

        return result

    def begin_message_session(
        self,
        request: SpeakRequest,
        window_lease: WindowReadyLease | None = None,
    ) -> ActiveMessageSession | None:
        """Claim the FIFO head as the sole active logical message.

        Args:
            request: Original FIFO request to claim for this session.
            window_lease: Validated Qt lease required for projection, when applicable.

        Returns:
            The claimed active session, or ``None`` when it is terminal or stale.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:

            # Session guard: check active session or prior terminal state
            is_internal_replay = bool(request.get("internalReplay"))
            terminal_before_session = (
                self.is_speak_terminal(str(request["id"])) and not is_internal_replay
            )

            # Conditional check: evaluate domain preconditions and invariants
            if self.active_session is not None or terminal_before_session:
                return None

            # Lease validation: verify current Qt window lease
            if window_lease is not None and not self.window_lease_is_current(
                window_lease
            ):
                return None

            # Session initialization: create ActiveMessageSession instance
            self._session_generation += 1
            muted = self.is_muted(request=request)
            session = ActiveMessageSession(
                request=request,
                generation=self._session_generation,
                muted=muted,
                window_lease=window_lease,
            )

            # Conditional check: evaluate domain preconditions and invariants
            if not muted and not request.get("manualSpeech"):
                session.tts = TtsBatchSession(str(request["id"]), session.generation)

            self.active_session = session
            awaiting_session = self.awaiting_window_speak_id == session.speak_id

            # Conditional check: evaluate domain preconditions and invariants
            if awaiting_session:
                self.awaiting_window_speak_id = ""

            self._replay_pending = False
            self.presentation_cancel_event.clear()
            self.active_speak_id = session.speak_id

            show_message = bool(request.get("showMessage", True))
            hide_when_muted = bool(request.get("hideWhenMuted", False))

            # Conditional check: evaluate domain preconditions and invariants
            if muted and hide_when_muted:
                show_message = False

            # Visual state configuration: set active display text and emotion
            if show_message:
                self.active_text = str(request.get("text", ""))
                self.active_display_text = str(
                    request.get("displayText", self.active_text)
                )
                self.active_emotion = str(request.get("emotion", ""))

            else:
                self.active_text = ""
                self.active_display_text = ""
                self.active_emotion = ""

            manual_speech = bool(request.get("manualSpeech"))

            # Conditional check: evaluate domain preconditions and invariants
            if manual_speech or not show_message:
                self.state = self.ambient_state

            # Conditional check: evaluate domain preconditions and invariants
            elif muted:
                self.state = "muted_replay"

            else:
                self.state = "preparing"

            self.last_activity = time.monotonic()

            return session

    def session_accepts(
        self, session: ActiveMessageSession, generation: int | None = None
    ) -> bool:
        """Guard every asynchronous result against STOP and session replacement.

        Args:
            session: Active session expected to retain ownership.
            generation: Optional producer generation to validate against the session.

        Returns:
            Whether the session remains active, uncancelled, and generation-current.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            token = session.generation if generation is None else generation
            session_is_active = self.active_session is session
            session_is_cancelled = session.cancelled.is_set()
            generation_is_current = token == session.generation

            # Conditional check: evaluate domain preconditions and invariants
            if not session_is_active:
                return False

            # Conditional check: evaluate domain preconditions and invariants
            if session_is_cancelled:
                return False

            return generation_is_current

    def close_message_session(
        self,
        session: ActiveMessageSession,
        status: str,
        *,
        preserve_visual: bool = False,
    ) -> None:
        """Close one message without ever clearing a newer active session.

        Args:
            session: Session that may relinquish the active lifecycle slot.
            status: Terminal status applied when the retained speak is not cancelled.
            preserve_visual: Whether to retain the current visual projection state.

        Returns:
            None: The session is closed only when it still owns the active slot.
        """

        # State guard: verify lifecycle status preconditions
        if status == "DONE":
            # Concurrency control: acquire lock for thread-safe state mutation
            with self.lock:
                # Conditional check: evaluate domain preconditions and invariants
                if self.active_session is not session:
                    return

                session.natural_close_started = True

            self._wait_for_composer_hold(session)

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            # Conditional check: evaluate domain preconditions and invariants
            if self.active_session is not session:
                return

            # Conditional check: evaluate domain preconditions and invariants
            if not self._restore_replay_record_locked(session.request):
                # State guard: verify lifecycle status preconditions
                if status == "DONE":
                    result = self.instance_lifecycle.terminalize(
                        session.speak_id, InstanceTerminalState.SPEAKED
                    )

                    # Conditional check: evaluate domain preconditions and invariants
                    if result is not None:
                        self._set_instance_record_status_locked(
                            session.speak_id, "DONE"
                        )

                # State guard: verify lifecycle status preconditions
                elif status == "ERROR":
                    self._cancel_instance_locked(session.speak_id, status="ERROR")

                # State guard: verify lifecycle status preconditions
                elif status == "CANCELLED":
                    self._cancel_instance_locked(session.speak_id)

                else:
                    self._set_instance_record_status_locked(session.speak_id, status)

            self.processing_speak_ids.discard(session.speak_id)
            self.processing_emotions.pop(session.speak_id, None)
            self.clear_progressive_audio(session.speak_id)
            self.active_session = None
            self.playback = None
            self.pending_playback = None
            session.release_composer_hold()

            # Visual cleanup: reset presentation fields to ambient state
            if not preserve_visual:
                self.state = self.ambient_state
                self.active_text = ""
                self.active_display_text = ""
                self.active_emotion = ""
                self.active_speak_id = ""
                self.playback_natural_end_at = 0.0
                self.muted_visual_deadline = 0.0

            session.presentation_done.set()

    def _is_historical_replay_request(self, request: SpeakRequest) -> bool:
        """Return whether a request is the retained-identity replay overlay.

        Args:
            request: Queue request whose replay metadata is inspected.

        Returns:
            bool: Whether the request is a historical replay, excluding other
            internal identity reuses such as embedded-file narration.
        """

        return bool(request.get("internalReplay")) and request.get("sourcePhase") == "replay"

    def _restore_replay_record_locked(self, request: SpeakRequest) -> bool:
        """Restore a retained record after its transient replay overlay ends.

        Args:
            request: Historical replay request carrying the retained state.

        Returns:
            bool: Whether a retained historical replay record was restored.

        The caller owns ``self.lock``. This deliberately projects only the
        retained diagnostic record; the original terminal lifecycle result is
        never cancelled or replaced.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if not self._is_historical_replay_request(request):
            return False

        speak_id = str(request.get("id", ""))
        record = next(
            (item for item in self.speaks if item.get("id") == speak_id),
            None,
        )
        self._replay_pending = False

        # Conditional check: evaluate domain preconditions and invariants
        if record is None:
            return False

        response = request.get("response")
        replay_response = None if response is None else str(response)
        self._set_instance_record_status_locked(
            speak_id,
            str(request.get("replayStatus", "")),
            error=str(request.get("replayError", "")),
            response=replay_response,
        )

        return True

    def restore_replay_record(self, request: SpeakRequest) -> bool:
        """Restore retained state for a historical replay outside a session.

        Args:
            request: Historical replay request being completed or failed.

        Returns:
            bool: Whether the retained replay record was restored.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            return self._restore_replay_record_locked(request)

    def _wait_for_composer_hold(self, session: ActiveMessageSession) -> None:
        """Wait for an open exact-message composer hold without owning the shared lock.

        Args:
            session: Active message session whose natural close may be held.

        Returns:
            None: The method returns after the hold resolves or the session stops.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            # Conditional check: evaluate domain preconditions and invariants
            if self.active_session is not session or not session.composer_hold_open:
                return

            release_event = session.composer_hold_released

        release_event.wait()

    def cancel_processing(self) -> int:
        """Cancel active synthesis jobs and discard any result produced afterward.

        Args:
            No arguments are accepted.

        Returns:
            Number of processing speak identifiers cancelled by this transition.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            cancelled_ids = set(self.processing_speak_ids)

            self.processing_speak_ids.clear()
            self.processing_emotions.clear()

            # Iteration: process speak instances sequentially
            for speak_id in cancelled_ids:
                self.clear_progressive_audio(speak_id)
                self._cancel_instance_locked(speak_id)

            self.last_activity = time.monotonic()

            return len(cancelled_ids)

    def is_speak_terminal(self, speak_id: str) -> bool:
        """Return whether a logical speak must discard all late internal work.

        Args:
            speak_id: Logical message identifier whose retained status is inspected.

        Returns:
            Whether the retained speak has any terminal lifecycle result.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            speak = next(
                (item for item in self.speaks if item.get("id") == speak_id), {}
            )
            retained_terminal = speak.get("status") in {
                "CANCELLED",
                "DEPRECATED",
                "DONE",
                "ERROR",
                "RESPONSED",
            }

            # Conditional check: evaluate domain preconditions and invariants
            if retained_terminal:
                return True

            # Exception safety: execute operation within error boundary
            try:
                result = self.instance_lifecycle.result(speak_id)

            # Key error handling: handle missing lookup entity
            except KeyError:
                return False

            return result is not None

    def stop_window_owned_speak(self) -> str | None:
        """Stop only a session already projected into the dead Qt window.

        ``active_speak_id`` may temporarily describe preactivation/thinking work
        that has not claimed a PID lease. A window respawn must preserve that
        logical FIFO head so it can retry the same ID against the replacement.

        Args:
            No arguments are accepted.

        Returns:
            str | None: Cancelled speak identifier, or ``None`` without an owned session.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            # Conditional check: evaluate domain preconditions and invariants
            if self.active_session is None:
                return None

            return self.stop_active_speak()

    def stop_active_speak(self) -> str | None:
        """Cancel the complete active generation, close its bubble, then release FIFO.

        This is the sole STOP transition used by both ``/stop-current-message``
        and legacy destructive ``/pause``. There is deliberately no resumable
        cursor or paused state.

        Args:
            No arguments are accepted.

        Returns:
            str | None: Cancelled speak identifier, or ``None`` when no work is active.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            session = self.active_session
            pending_speak_id = next(iter(self.processing_speak_ids), None)
            speak_id = (
                session.speak_id

                # Conditional check: evaluate domain preconditions and invariants
                if session is not None
                else (
                    self.active_speak_id
                    or self.awaiting_window_speak_id
                    or pending_speak_id
                )
                or None
            )

            # Identity check: verify instance ID invariants
            if speak_id is None:
                return None

            # Replay restoration: restore historical record if session was an internal replay
            if session is not None and self._is_historical_replay_request(
                session.request
            ):
                self._restore_replay_record_locked(session.request)

            else:
                self._cancel_instance_locked(speak_id)

            # Resource cleanup: reset active processing, player, and visual fields
            self.processing_speak_ids.discard(speak_id)
            self.processing_emotions.pop(speak_id, None)
            self.presentation_cancel_event.set()

            # Identity check: verify instance ID invariants
            if self.awaiting_window_speak_id == speak_id:
                self.awaiting_window_speak_id = ""
                self.window_wait_cancelled.set()

            # Conditional check: evaluate domain preconditions and invariants
            if session is not None:
                session.cancel()
                self.active_session = None

            # Conditional check: evaluate domain preconditions and invariants
            elif self.playback is not None:
                self.playback.terminate()

            self.playback = None
            self.pending_playback = None
            self.clear_progressive_audio(speak_id)
            self.state = self.ambient_state
            self.active_text = ""
            self.active_display_text = ""
            self.active_emotion = ""
            self.active_speak_id = ""
            self.playback_natural_end_at = 0.0
            self.muted_visual_deadline = 0.0

            return speak_id

    def start_registered_playback(
        self,
        speak_id: str,
        starter: Callable[[], PlaybackProcess],
    ) -> PlaybackProcess | None:
        """Start and publish a player atomically against terminal STOP.

        Args:
            speak_id: Logical message identifier that must still own playback.
            starter: Deferred player constructor executed while holding the session lock.

        Returns:
            Registered player, or ``None`` when STOP or replacement wins the race.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            session = self.active_session
            different_active_session = (
                session is not None and session.speak_id != speak_id
            )
            allow_terminal_replay = session is not None and bool(
                session.request.get("internalReplay")
            )
            terminal_before_start = self.is_speak_terminal(speak_id)

            # Conditional check: evaluate domain preconditions and invariants
            if (
                terminal_before_start and not allow_terminal_replay
            ) or different_active_session:
                return None

            playback = starter()

            # Conditional check: evaluate domain preconditions and invariants
            if session is not None and session.tts is not None:
                # Conditional check: evaluate domain preconditions and invariants
                if not session.tts.register_player(playback, session.generation):
                    return None

            self.playback = playback

            session_no_longer_active = session is not None and not self.session_accepts(
                session
            )
            terminal_after_start = self.is_speak_terminal(speak_id)

            # Conditional check: evaluate domain preconditions and invariants
            if (
                terminal_after_start and not allow_terminal_replay
            ) or session_no_longer_active:
                playback.terminate()
                self.playback = None

                return None

            return playback

    def begin_thinking(self, speak_id: str = "") -> None:
        """Show a thinking state when playback does not own presentation.

        Args:
            speak_id (str): Optional associated speak-job identifier.

        Returns:
            None: Thinking state is projected when no active playback owns presentation.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            # Conditional check: evaluate domain preconditions and invariants
            if not self.playback or self.playback.poll() is not None:
                self.state = "thinking"
                self.active_text = "Pensando…"
                self.active_emotion = "thinking"
                self.active_display_text = self.active_text
                self.active_speak_id = speak_id
                self.last_activity = time.monotonic()

    def finish_thinking(self) -> None:
        """Restore ambient state after a visible thinking turn.

        Args:
            No arguments are accepted.

        Returns:
            None: Ambient state replaces the transient thinking projection.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            # State guard: verify lifecycle status preconditions
            if self.state == "thinking":
                self.state = self.ambient_state
                self.active_text = ""
                self.active_emotion = ""
                self.active_display_text = ""
                self.active_speak_id = ""

    def has_active_work(self) -> bool:
        """Determine whether TTL shutdown would interrupt active work.

        Args:
            No arguments are accepted.

        Returns:
            bool: Whether synthesis, playback, or a transient state is active.
        """

        # Concurrency control: acquire lock for thread-safe state mutation
        with self.lock:
            playback_active = self.playback is not None and self.playback.poll() is None
            request_work_active = self.requests.has_unfinished_work()

            return bool(
                request_work_active
                or self.pending_playback
                or playback_active
                or self.state in {"thinking", "preparing", "speaking"}
            )

    def idle_expired(self, now: float | None = None) -> bool:
        """Determine whether idle TTL elapsed after all active work drained.

        Args:
            now (float | None): Monotonic timestamp override, or ``None`` now.

        Returns:
            bool: Whether the daemon may stop for idleness.
        """
        current = time.monotonic() if now is None else now

        return (
            current - self.last_activity >= IDLE_TTL_SECONDS
            and not self.has_active_work()
        )
