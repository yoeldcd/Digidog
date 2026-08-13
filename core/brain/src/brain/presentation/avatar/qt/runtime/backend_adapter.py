# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Qt transport adapter bound to toolkit-neutral projection and interaction policy."""
from __future__ import annotations

import json
import time
from typing import Any
from urllib.request import Request, urlopen

from brain.infrastructure.voice.daemon.daemon_client import VOICE_DAEMON_URL
from brain.presentation.avatar.communication.projection.daemon_status import DaemonStatusProjection
from brain.presentation.avatar.interactivity.presentation_state import (
    AvatarRuntimeState,
    ProjectedMessageState,
)
from brain.presentation.avatar.interactivity.interaction_controller import (
    AvatarCommand,
    AvatarControlIntent,
    InteractionController,
    ReactionIntent,
    ReplayTarget,
)
from brain.presentation.avatar.window.config import DAEMON_LOSS_GRACE_SECONDS


class QtBackendAdapterMixin:
    """Adapt HTTP and Qt events without duplicating message policy."""

    def _post(self, path: str, payload: dict[str, Any] | None = None) -> None:
        """Send an asynchronous HTTP POST request to the local voice daemon.

        Args:
            path (str): Relative endpoint path on the voice daemon server.
            payload (dict[str, Any] | None): Optional JSON payload body dictionary.

        Returns:
            None.
        """
        body = json.dumps(payload or {}).encode("utf-8")
        request = Request(
            f"{VOICE_DAEMON_URL}{path}",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        # Exception safety: execute operation within protected error boundary
        try:
            urlopen(request, timeout=.5).close()

        # System error handling: handle operating system or IO failure
        except OSError:
            pass


    def _replay_target(self) -> ReplayTarget:
        """Describe the exact message currently projected in the bubble.

        Returns:
            ReplayTarget: Immutable replay target object for the active message.
        """
        return ReplayTarget(
            speak_id=self.current_message_id,
            audio_name=self.current_audio_name,
            has_embedded_file=self.current_has_embedded_file,
            manual_speech=self.current_manual_speech,
            browsing_history=self.history_browsing,
        )

    def _interaction_state(self) -> ProjectedMessageState:
        """Normalize adapter caches into the shared interaction projection.

        Polling updates ``presentation_state`` atomically.  The compatibility
        fields remain writable for embedded callers, so an owned legacy
        presentation is projected here before shared policy chooses STOP.

        Returns:
            ProjectedMessageState: Current projected message state snapshot.
        """

        # State guard: verify component lifecycle state preconditions
        if self.presentation_state.owns_active_presentation or not self.active_presentation_owned:
            return self.presentation_state

        # Exception safety: execute operation within protected error boundary
        try:
            runtime_state = AvatarRuntimeState(self.state)

        # Validation handling: handle invalid input domain error
        except ValueError:
            runtime_state = AvatarRuntimeState.AWAITING
        return ProjectedMessageState(
            runtime_state=runtime_state,
            active_speak_id=self.active_speak_id or self.current_message_id,
            playback_active=self.playback_active or self.active_presentation_owned,
            progressive_playback_active=self.progressive_playback_active,
            has_embedded_file=self.current_has_embedded_file,
            manual_speech=self.current_manual_speech,
        )

    def _playback_is_active(self) -> bool:
        """Return shared logical presentation ownership.

        Returns:
            bool: True if playback is currently active.
        """
        return self._interaction_state().owns_active_presentation

    def _release_active_presentation(self) -> None:
        """Project terminal STOP immediately while the daemon advances FIFO.

        Returns:
            None
        """
        self.active_speak_id = ""
        self.active_presentation_owned = False
        self.playback_active = False
        self.progressive_playback_active = False
        self.presentation_state = self.presentation_state.__class__()
        self._set_state("awaiting", emotion="", speaking_active=False, processing=False)

    def _execute_avatar_command(self, command: AvatarCommand) -> None:
        """Deliver one shared command and apply only Qt presentation effects.

        Args:
            command (AvatarCommand): High-level avatar control command to execute.

        Returns:
            None
        """

        # Conditional check: evaluate domain preconditions and invariants
        if command.payload:
            self._post(command.endpoint, dict(command.payload))
        else:
            self._post(command.endpoint)

        # Conditional check: evaluate domain preconditions and invariants
        if command.intent is AvatarControlIntent.STOP:
            self._release_active_presentation()
            self._dismiss_bubble()

    def _replay_projected_message(self) -> None:
        """PLAY or REPLAY the exact currently projected message.

        Executes the primary click interaction for the active message state,
        replaying audio or displaying the active message.

        Args:
            None.

        Returns:
            None: Primary interaction command is dispatched to the backend.
        """
        command = InteractionController.primary_click(
            self._interaction_state(),
            self._replay_target(),
        )
        self._execute_avatar_command(command)

    def _activate_message_control(self) -> None:
        """Map one central-control click through shared interaction policy.

        Dispatches primary click commands according to the current projected
        message state and target conversation identity.

        Args:
            None.

        Returns:
            None: Interaction command is posted to the daemon adapter.
        """
        command = InteractionController.primary_click(
            self._interaction_state(),
            self._replay_target(),
        )
        self._execute_avatar_command(command)

    def _avatar_click(self) -> None:
        """Disambiguate one-click control from idle-only double-click reaction.

        Handles single and double clicks on the avatar widget, triggering reactions
        when idle or controlling message playback when active.

        Args:
            None.

        Returns:
            None: Click timer or interaction command is triggered.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if self.avatar_click_timer.isActive():
            self.avatar_click_timer.stop()

            # Conditional check: evaluate domain preconditions and invariants
            if self._playback_is_active():
                reaction = self.reaction_bag.draw_reaction()
                command = InteractionController.double_click(
                    self._interaction_state(),
                    ReactionIntent(reaction.message, reaction.animation),
                )
                self._execute_avatar_command(command)
            else:
                self._speak_reaction()
            return
        self.avatar_click_timer.start()

    def _commit_avatar_click(self) -> None:
        """Apply the same one-click contract as the central control.

        Executes single-click message control when the avatar click timer elapses.

        Args:
            None.

        Returns:
            None: Primary message control action is activated.
        """
        self._activate_message_control()

    def _speak_reaction(self) -> None:
        """Compatibility entrypoint for one idle shared reaction command.

        Draws a random reaction phrase and animation, sending a double-click command
        to the avatar backend.

        Args:
            None.

        Returns:
            None: Reaction speech command is executed.
        """
        reaction = self.reaction_bag.draw_reaction()
        command = InteractionController.double_click(
            self._interaction_state(),
            ReactionIntent(reaction.message, reaction.animation),
        )
        self._execute_avatar_command(command)

    def _poll(self) -> None:
        """Project one typed daemon snapshot into Qt views.

        Queries the daemon HTTP /status route, normalizes the response payload,
        and updates avatar animations, speech bubble text, theme, and control meters.

        Args:
            None.

        Returns:
            None: Qt avatar window presentation is synchronized with daemon state.
        """

        # Exception safety: execute operation within protected error boundary
        try:
            # Context management: acquire managed resource scope
            with urlopen(f"{VOICE_DAEMON_URL}/status", timeout=.2) as response:
                payload = json.loads(response.read())

        # Failure recovery: handle execution or transport exception
        except Exception:
            # Conditional check: evaluate domain preconditions and invariants
            if time.monotonic() - self.last_seen >= DAEMON_LOSS_GRACE_SECONDS:
                self.close()
            return
        status = DaemonStatusProjection.from_mapping(payload)

        # Identity validation: check canonical message or instance identifier
        if self.daemon_instance_id and status.instance_id != self.daemon_instance_id:
            self.close()
            return
        self.last_seen = time.monotonic()

        # State guard: verify component lifecycle state preconditions
        if status.theme_mode != self._theme_mode:
            self._theme_mode = status.theme_mode
            self.bubble.set_theme(status.theme_mode)
            self.reply_window.set_theme(status.theme_mode)

            # Guard clause: verify required active entity presence
            if self.backlog_window is not None:
                self.backlog_window.set_theme(status.theme_mode)
        presentation = status.presentation()
        self.presentation_state = presentation
        self.playback_active = presentation.playback_active
        self.progressive_playback_active = presentation.progressive_playback_active
        self.active_speak_id = presentation.active_speak_id
        self.active_presentation_owned = presentation.owns_active_presentation
        self.controls.set_state(presentation.owns_active_presentation, presentation.mute_mode)
        self.controls.set_queue_depth(presentation.queue_depth)
        self.bubble.set_remaining_seconds(presentation.visual_remaining_seconds)
        self._set_state(
            presentation.runtime_state.value,
            emotion=presentation.emotion,
            processing=presentation.processing_indicator_active,
            processing_emotion=presentation.processing_emotion,
            speaking_active=presentation.speaking_animation_active,
        )

        # State guard: verify component lifecycle state preconditions
        if presentation.runtime_state.value in {"thinking", "preparing"}:
            return
        self._set_text(
            presentation.display_text,
            emotion=presentation.emotion,
            message_id=presentation.active_speak_id,
            consumer_path=presentation.consumer_path,
            history_count=max(1, presentation.history_count),
            codex_thread_id=presentation.codex_thread_id,
            has_embedded_file=presentation.has_embedded_file,
            manual_speech=presentation.manual_speech,
        )
