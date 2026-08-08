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
from brain.infrastructure.voice.daemon.runtime_state import IDLE_TTL_SECONDS, estimated_speech_seconds
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
        with self.lock:
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
        with self.lock:
            if self.cancelled.is_set() or generation != self.generation:
                player.terminate()
                return False
            self.player = player
            return True

    def release_player(self, player: PlaybackProcess) -> None:
        """Forget a completed player without clearing a newer registration.

        Args:
            player: Completed playback process requesting release from the session.
        """
        with self.lock:
            if self.player is player:
                self.player = None

    def cancel(self) -> None:
        """Invalidate work, terminate playback, and release batch waiters."""
        with self.lock:
            self.cancelled.set()
            self.generation += 1
            if self.player is not None:
                self.player.terminate()
                self.player = None
            while True:
                try:
                    self.batches.get_nowait()
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
    """

    request: SpeakRequest
    generation: int
    muted: bool
    cancelled: threading.Event = field(default_factory=threading.Event)
    presentation_done: threading.Event = field(default_factory=threading.Event)
    tts: TtsBatchSession | None = None
    window_lease: WindowReadyLease | None = None

    @property
    def speak_id(self) -> str:
        """Return the stable logical message identifier.

        Returns:
            Stable speak identifier extracted from the original request.
        """

        return str(self.request["id"])

    def cancel(self) -> None:
        """Terminally cancel presentation and every private TTS batch."""
        self.cancelled.set()
        self.presentation_done.set()

        if self.tts is not None:
            self.tts.cancel()


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
        """
        with self.lock:
            self.window_supervisor = supervisor

    def register_window_process(self, pid: int) -> None:
        """Publish the only child PID eligible to acknowledge this generation.

        Args:
            pid: Process identifier for the spawned avatar window.
        """
        with self.lock:
            self.current_window_pid = int(pid)
            self.window_pids = [int(pid)]

    def mark_window_ready(self, pid: int | None = None) -> bool:
        """Accept readiness only from the supervisor's current live child PID.

        Args:
            pid: Process identifier reported by the ready window, when available.

        Returns:
            Whether the readiness signal belongs to the current process lease.
        """
        with self.lock:
            supervisor = self.window_supervisor
            live_pid = supervisor.pid if supervisor is not None else self.current_window_pid
            if supervisor is not None:
                if pid is None or pid != live_pid or pid != self.current_window_pid:
                    return False
            elif self.current_window_pid is not None and pid != self.current_window_pid:
                return False
            self.last_activity = time.monotonic()
            self.ready_window_pid = pid
            self.window_ready.set()

            return True

    def prepare_for_window_spawn(self) -> int:
        """Invalidate the prior PID lease and open a fresh spawn generation."""
        with self.lock:
            self.window_generation += 1
            self.ready_window_pid = None
            self.current_window_pid = None
            self.window_pids = []
            self.window_ready.clear()
            self.window_wait_cancelled.clear()

            return self.window_generation

    def window_lease_is_current(self, lease: WindowReadyLease | None) -> bool:
        """Validate generation and PID against the supervisor's live process."""
        if lease is None:
            return self.window_supervisor is None
        with self.lock:
            if (
                not self.window_ready.is_set()
                or lease.generation != self.window_generation
                or lease.pid != self.ready_window_pid
            ):
                return False
            if self.window_supervisor is None:
                return self.current_window_pid is None or lease.pid == self.current_window_pid
            return lease.pid == self.current_window_pid == self.window_supervisor.pid

    def wait_for_window(self, request: SpeakRequest) -> WindowReadyLease | None:
        """Acquire an interruptible, PID-bound lease before message projection.

        Args:
            request: FIFO request whose speak identifier waits for a live window.

        Returns:
            Current Qt window lease, or ``None`` when waiting is terminally cancelled.
        """
        speak_id = str(request["id"])
        with self.lock:
            self.awaiting_window_speak_id = speak_id
            self.window_wait_cancelled.clear()
        while True:
            if self.window_ready.wait(timeout=0.025):
                with self.lock:
                    lease = WindowReadyLease(self.ready_window_pid, self.window_generation)
                if self.window_lease_is_current(lease):
                    return lease
                with self.lock:
                    if self.ready_window_pid == lease.pid and self.window_generation == lease.generation:
                        self.ready_window_pid = None
                        self.window_ready.clear()
            with self.lock:
                if self.stop_requested or self.window_wait_cancelled.is_set() or self.is_speak_terminal(speak_id):
                    if self.awaiting_window_speak_id == speak_id:
                        self.awaiting_window_speak_id = ""
                    return None

    def record_supervision_error(self, error: Exception) -> None:
        """Retain a bounded diagnostic trail without killing supervision."""
        with self.lock:
            self.supervision_errors.append(str(error))
            del self.supervision_errors[:-10]

    def request_daemon_stop(self) -> None:
        """Terminally cancel active/waiting work and release readiness waits."""
        with self.lock:
            self.stop_requested = True
            self.window_wait_cancelled.set()
            self.stop_active_speak()

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
        with self.lock:
            if self.active_session is not None or self.is_speak_terminal(str(request["id"])):
                return None
            if window_lease is not None and not self.window_lease_is_current(window_lease):
                return None
            self._session_generation += 1
            muted = self.is_muted(request=request)
            session = ActiveMessageSession(
                request=request,
                generation=self._session_generation,
                muted=muted,
                window_lease=window_lease,
            )
            if not muted and not request.get("manualSpeech"):
                session.tts = TtsBatchSession(str(request["id"]), session.generation)
            self.active_session = session
            if self.awaiting_window_speak_id == session.speak_id:
                self.awaiting_window_speak_id = ""
            self._replay_pending = False
            self.presentation_cancel_event.clear()
            self.active_speak_id = session.speak_id

            show_message = bool(request.get("showMessage", True)) and not (
                muted and bool(request.get("hideWhenMuted", False))
            )

            if show_message:
                self.active_text = str(request.get("text", ""))
                self.active_display_text = str(request.get("displayText", self.active_text))
                self.active_emotion = str(request.get("emotion", ""))
            else:
                self.active_text = ""
                self.active_display_text = ""
                self.active_emotion = ""

            if request.get("manualSpeech") or not show_message:
                self.state = self.ambient_state
            elif muted:
                self.state = "muted_replay"
            else:
                self.state = "preparing"
            self.last_activity = time.monotonic()

            return session

    def session_accepts(self, session: ActiveMessageSession, generation: int | None = None) -> bool:
        """Guard every asynchronous result against STOP and session replacement.

        Args:
            session: Active session expected to retain ownership.
            generation: Optional producer generation to validate against the session.

        Returns:
            Whether the session remains active, uncancelled, and generation-current.
        """
        with self.lock:
            token = session.generation if generation is None else generation
            return (
                self.active_session is session
                and not session.cancelled.is_set()
                and token == session.generation
            )

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
        """

        with self.lock:
            if self.active_session is not session:
                return
            retained = next((item for item in self.speaks if item.get("id") == session.speak_id), None)

            if retained is not None and retained.get("status") != "CANCELLED":
                retained["status"] = status

            self.processing_speak_ids.discard(session.speak_id)
            self.processing_emotions.pop(session.speak_id, None)
            self.clear_progressive_audio(session.speak_id)
            self.active_session = None
            self.playback = None
            self.pending_playback = None

            if not preserve_visual:
                self.state = self.ambient_state
                self.active_text = ""
                self.active_display_text = ""
                self.active_emotion = ""
                self.active_speak_id = ""
                self.playback_natural_end_at = 0.0
                self.muted_visual_deadline = 0.0
            session.presentation_done.set()

    def cancel_processing(self) -> int:
        """Cancel active synthesis jobs and discard any result produced afterward.

        Returns:
            Number of processing speak identifiers cancelled by this transition.
        """
        with self.lock:
            cancelled_ids = set(self.processing_speak_ids)

            for speak in self.speaks:
                if speak.get("id") in cancelled_ids:
                    speak["deprecated"] = "true"
                    speak["status"] = "CANCELLED"
            self.processing_speak_ids.clear()
            self.processing_emotions.clear()

            for speak_id in cancelled_ids:
                self.clear_progressive_audio(speak_id)
            self.last_activity = time.monotonic()

            return len(cancelled_ids)

    def is_speak_terminal(self, speak_id: str) -> bool:
        """Return whether a logical speak must discard all late internal work.

        Args:
            speak_id: Logical message identifier whose retained status is inspected.

        Returns:
            Whether the retained speak has a terminal cancellation or error status.
        """
        with self.lock:
            speak = next((item for item in self.speaks if item.get("id") == speak_id), {})
            return speak.get("status") in {"CANCELLED", "DEPRECATED", "ERROR"}

    def stop_window_owned_speak(self) -> str | None:
        """Stop only a session already projected into the dead Qt window.

        ``active_speak_id`` may temporarily describe preactivation/thinking work
        that has not claimed a PID lease. A window respawn must preserve that
        logical FIFO head so it can retry the same ID against the replacement.
        """
        with self.lock:
            if self.active_session is None:
                return None
            return self.stop_active_speak()

    def stop_active_speak(self) -> str | None:
        """Cancel the complete active generation, close its bubble, then release FIFO.

        This is the sole STOP transition used by both ``/stop-current-message``
        and legacy destructive ``/pause``. There is deliberately no resumable
        cursor or paused state.
        """
        with self.lock:
            session = self.active_session
            pending_speak_id = next(iter(self.processing_speak_ids), None)
            speak_id = session.speak_id if session is not None else (
                self.active_speak_id or self.awaiting_window_speak_id or pending_speak_id
            )

            if speak_id is None:
                return None
            speak = next((item for item in self.speaks if item.get("id") == speak_id), None)

            if speak is not None:
                speak["deprecated"] = "true"
                speak["status"] = "CANCELLED"
                speak["error"] = ""

            self.processing_speak_ids.discard(speak_id)
            self.processing_emotions.pop(speak_id, None)
            self.presentation_cancel_event.set()

            if self.awaiting_window_speak_id == speak_id:
                self.awaiting_window_speak_id = ""
                self.window_wait_cancelled.set()

            if session is not None:
                session.cancel()
                self.active_session = None

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

        with self.lock:
            session = self.active_session
            different_active_session = session is not None and session.speak_id != speak_id

            if self.is_speak_terminal(speak_id) or different_active_session:
                return None

            playback = starter()

            if session is not None and session.tts is not None:
                if not session.tts.register_player(playback, session.generation):
                    return None
            self.playback = playback

            session_no_longer_active = session is not None and not self.session_accepts(session)
            if self.is_speak_terminal(speak_id) or session_no_longer_active:
                playback.terminate()
                self.playback = None
                return None

            return playback

    def begin_thinking(self, speak_id: str = "") -> None:
        """Show a thinking state when playback does not own presentation.

        Args:
            speak_id (str): Optional associated speak-job identifier.
        """
        with self.lock:
            if not self.playback or self.playback.poll() is not None:
                self.state = "thinking"
                self.active_text = "Pensando…"
                self.active_emotion = "thinking"
                self.active_display_text = self.active_text
                self.active_speak_id = speak_id
                self.last_activity = time.monotonic()

    def finish_thinking(self) -> None:
        """Restore ambient state after a visible thinking turn."""
        with self.lock:
            if self.state == "thinking":
                self.state = self.ambient_state
                self.active_text = ""
                self.active_emotion = ""
                self.active_display_text = ""
                self.active_speak_id = ""

    def has_active_work(self) -> bool:
        """Determine whether TTL shutdown would interrupt active work.

        Returns:
            bool: Whether synthesis, playback, or a transient state is active.
        """
        with self.lock:
            playback_active = self.playback is not None and self.playback.poll() is None
            return bool(
                self.requests.unfinished_tasks
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
        return current - self.last_activity >= IDLE_TTL_SECONDS and not self.has_active_work()
