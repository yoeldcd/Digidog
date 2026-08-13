# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Qt message projection, history adaptation, and bubble coordination."""
from __future__ import annotations

import json
from urllib.request import urlopen

from PySide6.QtCore import QPoint

from dataclasses import dataclass

from brain.infrastructure.voice.daemon.daemon_client import VOICE_DAEMON_URL
from brain.presentation.avatar.communication.contracts.models import CodexThreadTargetDTO
from brain.presentation.avatar.interactivity.emotions import emotion_emoji
from brain.presentation.avatar.interactivity.history_controller import HistoryController, HistoryMessage
from brain.presentation.avatar.qt.avatar.geometry import (
    bubble_position, bubble_vertical_lane, clamp_bubble_position, reply_composer_geometry,
)


@dataclass(frozen=True, slots=True)
class QtHistoryMessage(HistoryMessage):
    """Qt-adapted history message supporting subscript access for legacy callers and tests.

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

    def __getitem__(self, key: str) -> object:
        """Allow subscript access for legacy dictionary key names.

        Args:
            key (str): Attribute or dictionary key name.

        Returns:
            object: Attribute value corresponding to key name.

        Raises:
            KeyError: If the key name is not recognized.
        """
        mapping = {
            "id": self.speak_id,
            "speak_id": self.speak_id,
            "displayText": self.display_text,
            "text": self.display_text,
            "display_text": self.display_text,
            "emotion": self.emotion,
            "consumerPath": self.consumer_path,
            "consumer_path": self.consumer_path,
            "codexThreadId": self.codex_thread_id,
            "codex_thread_id": self.codex_thread_id,
            "audioName": self.audio_name,
            "audio_name": self.audio_name,
            "hasEmbeddedFile": self.has_embedded_file,
            "has_embedded_file": self.has_embedded_file,
            "manualSpeech": self.manual_speech,
            "manual_speech": self.manual_speech,
        }

        # Conditional check: evaluate domain preconditions and invariants
        if key in mapping:
            return mapping[key]
        raise KeyError(key)


class QtMessageControllerMixin:
    """Mixin managing message display, history navigation, and bubble coordination.

    Handles active message formatting, animation triggers, history index tracking,
    and bubble geometry adjustments for the main Qt avatar presentation window.
    """


    def _set_text(
        self,
        text: str,
        emotion: str = "",
        message_id: str = "",
        consumer_path: str = "",
        history_count: int = 1,
        codex_thread_id: str = "",
        has_embedded_file: bool = False,
        manual_speech: bool = False,
    ) -> None:
        """Update active message state, bubble content, and visibility.

        Args:
            text (str): Message text displayed in the bubble.
            emotion (str): Emotion identifier for avatar animation.
            message_id (str): Unique speech/message identifier.
            consumer_path (str): File/component path for provenance display.
            history_count (int): Total count of retained history messages.
            codex_thread_id (str): Associated Codex thread ID if available.
            has_embedded_file (bool): Whether the message contains embedded file blocks.
            manual_speech (bool): Whether speech was requested manually.

        Returns:
            None.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if self.history_browsing:
            # Content check: validate message text payload
            if text:
                self.last_display_text = text
                self.last_message_id = message_id
                self.last_display_emotion = emotion
                self.last_consumer_path = consumer_path
                self.last_codex_thread_id = codex_thread_id
                self.last_has_embedded_file = has_embedded_file
                self.last_manual_speech = manual_speech
            self.history_count = max(1, history_count)
            return

        incoming_message = bool(message_id and message_id != self.current_message_id)

        # Conditional check: evaluate domain preconditions and invariants
        if incoming_message:
            self.history_browsing = False
            self.current_audio_name = ""
            self.message_reveal_latched = False
            self.dismissed_display_text = ""
            self.dismissed_message_id = ""

        # Content check: validate message text payload
        if not text:
            # Conditional check: evaluate domain preconditions and invariants
            if self.message_reveal_latched or self.current_has_embedded_file:
                return

            # Conditional check: evaluate domain preconditions and invariants
            if self.bubble.isVisible():
                # Conditional check: evaluate domain preconditions and invariants
                if not self.bubble_hide_timer.isActive():
                    self.bubble_hide_timer.start()
                return
            self.current_display_text = ""
            self.current_message_id = ""
            self.current_audio_name = ""
            self.current_codex_thread_id = ""
            self.current_has_embedded_file = False
            self.current_manual_speech = False
            self.dismissed_display_text = ""
            self.dismissed_message_id = ""
            return

        # Content check: validate message text payload
        if incoming_message or text != self.current_display_text:
            self.message_reveal_latched = False

        self.last_display_text = text
        self.last_message_id = message_id
        self.last_display_emotion = emotion
        self.last_consumer_path = consumer_path
        self.last_codex_thread_id = codex_thread_id
        self.last_has_embedded_file = has_embedded_file
        self.last_manual_speech = manual_speech
        self.history_count = max(1, history_count)

        previous = self.current_display_text
        previous_message_id = self.current_message_id
        self.current_display_text = text
        self.current_message_id = message_id
        self.current_codex_thread_id = codex_thread_id
        self.current_has_embedded_file = has_embedded_file
        self.current_manual_speech = manual_speech

        # Content check: validate message text payload
        if text == self.dismissed_display_text and message_id == self.dismissed_message_id:
            return

        # Content check: validate message text payload
        if text == previous and message_id == previous_message_id and self.bubble.isVisible():
            return

        # Content check: validate message text payload
        if incoming_message or text != previous:
            self.dismissed_display_text = ""
            self.dismissed_message_id = ""

        self.bubble_hide_timer.stop()
        was_visible = self.bubble.isVisible()
        self._set_bubble_message_anchored(
            text,
            emotion_emoji(emotion),
            consumer_path,
            history_index=0,
            history_total=self.history_count,
        )
        self.bubble.set_reply_available(bool(message_id))

        # Conditional check: evaluate domain preconditions and invariants
        if not was_visible:
            self._reposition_bubble(force=True)
        else:
            self._update_tail()

        self.bubble.show()
        self.bubble.raise_()
        self.controls.show()
        self.controls.raise_()

    def _toggle_last_message(self) -> None:
        """Toggle retained visual content without replaying or synthesizing.

        Returns:
            None.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if self.bubble.isVisible():
            self._dismiss_bubble()
            return

        # Content check: validate message text payload
        if not self.last_display_text:
            return

        self.dismissed_display_text = ""
        self.dismissed_message_id = ""
        self.current_display_text = self.last_display_text
        self.current_message_id = self.last_message_id
        self.current_has_embedded_file = self.last_has_embedded_file
        self.current_manual_speech = self.last_manual_speech
        self.message_reveal_latched = True
        self.bubble_hide_timer.stop()

        self._set_bubble_message_anchored(
            self.last_display_text,
            emotion_emoji(self.last_display_emotion),
            self.last_consumer_path,
            history_index=0,
            history_total=self.history_count,
            preserve_avatar_edge=True,
        )
        self.current_codex_thread_id = self.last_codex_thread_id
        self.bubble.set_reply_available(bool(self.current_message_id))
        self._reposition_bubble(force=True)
        self.bubble.show()
        self.bubble.raise_()

    def _message_history(self) -> list[HistoryMessage]:
        """Read emitted speaks without replaying or mutating daemon state.

        Returns:
            list[HistoryMessage]: Retained message projections.
        """

        # Exception safety: execute operation within error boundary
        try:
            # Context management: enter managed resource scope
            with urlopen(f"{VOICE_DAEMON_URL}/messages", timeout=.5) as response:
                payload = json.loads(response.read())

        # Failure recovery: handle execution or transport exception
        except Exception:
            return []

        audio_by_speak_id = {
            str(item.get("speakId", "")): str(item.get("name", ""))

            # Iteration: process sequence items
            for item in payload.get("messages", [])

            # Conditional check: evaluate domain preconditions and invariants
            if item.get("speakId") and item.get("name")
        }

        messages: list[HistoryMessage] = []

        # Iteration: process speak instances sequentially
        for item in payload.get("speaks", []):
            # Content check: validate message text payload
            if item.get("displayText") or item.get("text"):
                speak_id = str(item.get("id", ""))
                audio_name = audio_by_speak_id.get(speak_id, "")
                messages.append(
                    QtHistoryMessage(
                        speak_id=speak_id,
                        display_text=str(item.get("displayText") or item.get("text", "")),
                        emotion=str(item.get("emotion", "")),
                        consumer_path=str(item.get("consumerPath", "")),
                        codex_thread_id=str(item.get("codexThreadId", "")),
                        audio_name=audio_name,
                        has_embedded_file=bool(item.get("hasEmbeddedFile", False)),
                        manual_speech=bool(item.get("manualSpeech", False)),
                    )
                )

        return messages

    def _navigate_message(self, direction: int) -> None:
        """Browse newest-first history through the shared controller.

        Args:
            direction (int): Relative step direction (-1 for older, +1 for newer).

        Returns:
            None.
        """
        raw_history = self._message_history()
        history = [
            item if isinstance(item, HistoryMessage) else HistoryMessage.from_mapping(item)

            # Iteration: process sequence items
            for item in raw_history
        ]
        controller = HistoryController(history)
        projection = controller.navigate(self.current_message_id, direction)

        # Conditional check: evaluate domain preconditions and invariants
        if projection is None:
            return

        item = projection.message
        self.current_display_text = item.display_text
        self.current_message_id = item.speak_id
        self.current_audio_name = item.audio_name
        self.current_codex_thread_id = item.codex_thread_id
        self.current_has_embedded_file = item.has_embedded_file
        self.current_manual_speech = item.manual_speech
        self.message_reveal_latched = True
        self.history_browsing = projection.browsing_history

        newest = controller.newest()
        self.history_anchor_message_id = newest.message.speak_id if newest else ""
        self.bubble_hide_timer.stop()

        self._set_bubble_message_anchored(
            item.display_text,
            emotion_emoji(item.emotion),
            item.consumer_path,
            history_index=projection.storage_index,
            history_total=projection.total,
            preserve_avatar_edge=True,
        )
        self.bubble.set_reply_available(bool(item.speak_id))
        self.bubble.show()
        self.bubble.raise_()

    def _set_bubble_message_anchored(self, *args, preserve_avatar_edge: bool = False, **kwargs) -> None:
        """Resize content while preserving manual origin or automatic avatar justification.

        Args:
            *args: Positional arguments forwarded to bubble set_message.
            preserve_avatar_edge (bool): Whether to preserve the avatar edge during resize.
            **kwargs: Keyword arguments forwarded to bubble set_message.

        Returns:
            None.
        """
        was_visible = self.bubble.isVisible()
        old_geometry = self.bubble.frameGeometry()
        old_position = QPoint(old_geometry.topLeft())
        manual_bottom = old_geometry.bottom()
        manual_position = self._bubble_manual_position is not None
        above_avatar = was_visible and self._bubble_is_above_avatar()
        avatar_geometry = self.frameGeometry()
        lane = ""

        # Conditional check: evaluate domain preconditions and invariants
        if was_visible:
            screen = self.app.screenAt(self.frameGeometry().center()) or self.app.primaryScreen()

            # Conditional check: evaluate domain preconditions and invariants
            if screen is not None:
                lane, available_height = bubble_vertical_lane(
                    screen.availableGeometry(),
                    self.frameGeometry(),
                    old_geometry,
                    manual_position,
                )
                self.bubble.set_vertical_height_limit(bool(lane), available_height)
            self.bubble.set_vertical_placement(above_avatar)

        self.bubble.set_message(*args, **kwargs)

        # Conditional check: evaluate domain preconditions and invariants
        if not was_visible:
            return

        # Conditional check: evaluate domain preconditions and invariants
        if not manual_position:
            # Conditional check: evaluate domain preconditions and invariants
            if preserve_avatar_edge and above_avatar:
                anchored_bottom = avatar_geometry.top() - 1
                anchored_top = anchored_bottom - self.bubble.height() + 1
                self.bubble.move(old_position.x(), anchored_top)

            # Conditional check: evaluate domain preconditions and invariants
            elif preserve_avatar_edge:
                anchored_top = avatar_geometry.bottom() + 1
                self.bubble.move(old_position.x(), anchored_top)

            # Conditional check: evaluate domain preconditions and invariants
            elif above_avatar:
                self.bubble.move(
                    old_position.x(),
                    old_geometry.bottom() - self.bubble.height() + 1,
                )
            else:
                self.bubble.move(old_position)
            self._update_tail()
            return

        # Conditional check: evaluate domain preconditions and invariants
        if manual_position:

            # A user-selected bottom edge is the vertical authority across
            # message-specific height changes, regardless of tail direction.
            self.bubble.move(old_position.x(), manual_bottom - self.bubble.height() + 1)

        self._bubble_manual_position = QPoint(self.bubble.pos())
        self._bubble_manual_bottom = self.bubble.frameGeometry().bottom()
        self._update_tail()

    def _open_reply_composer(self) -> None:
        """Open a detached composer bound to the currently displayed speak.

        Returns:
            None.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if not self.current_message_id:
            return

        instance_id = self.current_message_id

        # Identity validation: check canonical message or instance identifier
        if getattr(self, "_reply_opening_instance_id", None) == instance_id:
            return

        self._reply_opening_instance_id = instance_id

        # Exception safety: execute operation within protected error boundary
        try:
            # Exception safety: execute operation within error boundary
            try:
                target = CodexThreadTargetDTO(
                    instance_id=instance_id,
                )

            # Validation error handling: convert invalid input to domain exception
            except ValueError:
                self.bubble.set_reply_available(False)
                return

            bubble = self.bubble.frameGeometry()
            screen = self.app.screenAt(bubble.center()) or self.app.primaryScreen()

            # Conditional check: evaluate domain preconditions and invariants
            if screen is None:
                return

            available = screen.availableGeometry()
            is_visible = getattr(self.reply_window, "isVisible", None)
            reply_was_hidden = not is_visible() if callable(is_visible) else True
            has_manual_geometry = (
                getattr(self.reply_window, "_manual_geometry", None) is not None
            )
            automatic_reply_open = reply_was_hidden and not has_manual_geometry
            geometry = reply_composer_geometry(
                available,
                bubble,
                self._bubble_is_above_avatar(),
                minimum_size=self.reply_window.safe_minimum_size(available),
                avatar=self.frameGeometry(),
                horizontal_margin=0 if automatic_reply_open else None,
            )
            self.reply_window.open_for(target, geometry)

            if automatic_reply_open:
                apply_automatic_geometry = getattr(
                    self.reply_window,
                    "apply_automatic_geometry",
                    None,
                )

                if callable(apply_automatic_geometry):
                    apply_automatic_geometry(
                        geometry,
                        preserve_horizontal_anchor=True,
                    )

        finally:
            # Identity validation: check canonical message or instance identifier
            if getattr(self, "_reply_opening_instance_id", None) == instance_id:
                self._reply_opening_instance_id = None

    def _bubble_is_above_avatar(self) -> bool:
        """Resolve vertical orientation solely from the current global window centers.

        Returns:
            bool: True if bubble center is above avatar center.
        """
        return self.bubble.frameGeometry().center().y() < self.frameGeometry().center().y()

    def _dismiss_bubble(self) -> None:
        """Dismiss active bubble and release active presentation if owned.

        Returns:
            None.
        """
        closing_history = self.history_browsing
        self.history_browsing = False
        self.history_anchor_message_id = ""

        # State guard: verify lifecycle status preconditions
        if not closing_history and self.active_presentation_owned and self.state in {"muted", "muted_replay"}:
            self._post("/stop-current-message")
            self._release_active_presentation()

        self.message_reveal_latched = False
        self.dismissed_display_text = self.current_display_text
        self.dismissed_message_id = self.current_message_id
        self.bubble_hide_timer.stop()
        self.bubble.hide()

    def _hide_bubble(self) -> None:
        """Hide bubble when not latched or containing embedded file blocks.

        Returns:
            None.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if self.message_reveal_latched or self.current_has_embedded_file:
            return

        self.bubble.hide()

        # Conditional check: evaluate domain preconditions and invariants
        if not self.underMouse():
            self.controls.set_expanded(False)

