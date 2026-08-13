# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Tk lifecycle and daemon-status projection adapter."""
from __future__ import annotations

import os
import time

from brain.presentation.avatar.communication.projection.daemon_status import DaemonStatusProjection
from brain.presentation.avatar.interactivity.presentation_state import AvatarRuntimeState, ProjectedMessageState
from brain.presentation.avatar.window.config import DAEMON_LOSS_GRACE_SECONDS, POLL_INTERVAL_MS, avatar_asset


class TkRuntimeAdapterMixin:
    """Bind typed daemon snapshots to Tk collaborators without policy duplication."""

    def _signal_window_ready(self) -> None:
        """Notify the daemon that the Tk window has completed initialization.

        Returns:
            None.
        """

        # Exception safety: execute operation within protected error boundary
        try:
            self.transport.post("/window-ready", {"pid": os.getpid()})

        # System error handling: handle operating system or IO failure
        except OSError:
            pass

    def _show(self) -> None:
        """Show the Tk window and resume its presentation polling.

        Returns:
            None.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if not self.is_visible:
            self.root.deiconify()
            self.is_visible = True

    def _hide(self) -> None:
        """Hide the Tk window without destroying its session state.

        Returns:
            None.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if self.is_visible:
            self.player.stop()
            self.root.withdraw()
            self.is_visible = False

    def _set_state(self, state: str, force: bool = False, emotion: str = "") -> None:
        """Project daemon state, mute state, and emotion into the Tk presentation.

        Args:
            state (str): Daemon state projected into the Tk window.
            force (bool): Whether to bypass the unchanged-state guard.
            emotion (str): Emotion key used to choose the processing glyph or animation.

        Returns:
            None.
        """
        changed = state != self.state or emotion != self.emotion
        self.state, self.emotion = state, emotion

        speaking = self.presentation.speaking_animation_active
        self.player.set_playing(self.presentation.owns_active_presentation)

        # Conditional check: evaluate domain preconditions and invariants
        if self.presentation.owns_active_presentation:
            self._show()

        self._apply_topmost()

        animation, fallback = self._animation_for_state(state, emotion)
        path = avatar_asset(animation, fallback_state=fallback)
        needs_recovery = self.player.displayed_path != str(path)

        # Conditional check: evaluate domain preconditions and invariants
        if (changed or force or needs_recovery) and path.is_file():
            self.player.load(path)

        self._set_processing_indicator(
            self.presentation.processing_indicator_active,
            self.presentation.processing_emotion,
        )
        self._set_queue_depth(self.presentation.queue_depth)

    def _animation_for_state(self, state: str, emotion: str) -> tuple[str, str]:
        """Resolve the GIF asset and emotion used for a daemon state.

        Args:
            state (str): Daemon state projected into the Tk window.
            emotion (str): Emotion key used to choose the processing glyph or animation.

        Returns:
            tuple[str, str]: Active animation key and fallback state key.
        """
        presentation = getattr(self, "presentation", None)
        audible = presentation.speaking_animation_active if presentation is not None else state == "speaking"

        # Conditional check: evaluate domain preconditions and invariants
        if audible:
            return emotion or "speaking", "speaking"

        # State guard: verify component lifecycle state preconditions
        if state == "working":
            return "working", "awaiting"

        return self.awaiting_quota_animation or "awaiting", "awaiting"

    def _poll(self) -> None:
        """Poll transport; presentation failures never consume daemon-loss grace.

        Returns:
            None.
        """

        # Exception safety: execute operation within protected error boundary
        try:
            payload = self.transport.status()

        # Failure recovery: handle execution or transport exception
        except Exception:
            # Conditional check: evaluate domain preconditions and invariants
            if time.monotonic() - self.last_seen >= DAEMON_LOSS_GRACE_SECONDS:
                self._shutdown_window()
                return

            self.root.after(POLL_INTERVAL_MS, self._poll)
            return

        projection = DaemonStatusProjection.from_mapping(payload)

        # Identity validation: check canonical message or instance identifier
        if self.daemon_instance_id and projection.instance_id != self.daemon_instance_id:
            self._shutdown_window()
            return

        self.last_seen = time.monotonic()

        # Exception safety: execute operation within protected error boundary
        try:
            self.presentation = projection.presentation()
            self.mute_mode = self.presentation.mute_mode
            self.player.set_muted(self.presentation.mute_mode != "off")
            self._set_state(self.presentation.runtime_state.value, emotion=self.presentation.emotion)
            self.message_controller.apply(self.presentation, self._set_text)

        # Failure recovery: handle execution or transport exception
        except Exception:
            pass

        self.root.after(POLL_INTERVAL_MS, self._poll)

    def _shutdown_window(self) -> None:
        """Stop callbacks, destroy the Tk window, and release presentation resources.

        Returns:
            None.
        """
        self.quota_client.close()
        self.player.stop()
        self.bubble_root.destroy()
        self.root.destroy()
