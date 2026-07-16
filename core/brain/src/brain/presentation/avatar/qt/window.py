# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""PySide6 avatar runtime connected to the existing voice daemon."""
from __future__ import annotations

import json
import os
import queue
import threading
import time
from datetime import datetime
from urllib.request import Request, urlopen

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QCursor, QMovie, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from brain.infrastructure.voice.daemon_client import VOICE_DAEMON_URL
from brain.infrastructure.codex.quota_client import CodexQuotaClient
from brain.presentation.avatar.communication.controller import AvatarReplyController
from brain.presentation.avatar.communication.models import CodexThreadTargetDTO
from brain.presentation.avatar.communication.message_store import AvatarMessageStore
from brain.presentation.avatar.communication.outbox_gateway import NativeOutboxGateway
from brain.presentation.avatar.communication.qt_reply_window import QtReplyWindow
from brain.presentation.avatar.communication.service import AvatarReplyService
from brain.presentation.avatar.window.config import DAEMON_LOSS_GRACE_SECONDS, INITIAL_HEIGHT, INITIAL_WIDTH, POLL_INTERVAL_MS, avatar_asset
from brain.presentation.avatar.interactivity.emotions import emotion_emoji
from brain.presentation.avatar.qt.markdown_bubble import QtMarkdownBubble
from brain.presentation.avatar.qt.controls import QtAvatarControls
from brain.presentation.avatar.interactivity.reactions import ReactionPhraseBag


def bubble_position(screen: QRect, avatar: QRect, bubble: QSize, gap: int = 18) -> QPoint:
    """Prefer above, then below; lateral placement is only a vertical-space fallback."""
    top_space = avatar.top() - screen.top()
    bottom_space = screen.bottom() - avatar.bottom()
    vertical_need = bubble.height() + gap
    if avatar.center().x() >= screen.center().x():
        aligned_x = avatar.right() - bubble.width()
    else:
        aligned_x = avatar.left()
    if top_space >= vertical_need:
        x, y = aligned_x, avatar.top() - bubble.height() - gap
    elif bottom_space >= vertical_need:
        x, y = aligned_x, avatar.bottom() + gap
    elif avatar.left() - screen.left() >= screen.right() - avatar.right():
        x, y = avatar.left() - bubble.width() - gap, avatar.center().y() - bubble.height() // 2
    else:
        x, y = avatar.right() + gap, avatar.center().y() - bubble.height() // 2
    margin = 18
    return QPoint(max(screen.left() + margin, min(x, screen.right() - bubble.width() - margin)),
                  max(screen.top() + margin, min(y, screen.bottom() - bubble.height() - margin)))


def quota_reset_label(timestamp: int, weekly: bool) -> str:
    if not timestamp:
        return "--" if weekly else "--:--"
    value = datetime.fromtimestamp(timestamp).astimezone()
    return value.strftime("%d %b").upper() if weekly else value.strftime("%H:%M")


def fit_avatar_frame(frame: QPixmap, available: QSize) -> QPixmap:
    if frame.isNull():
        return frame
    # GIF frames share one logical canvas. Cropping each alpha mask independently
    # makes the character pulse as the occupied pixels change between frames.
    return frame.scaled(available, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


class QtAvatarWindow(QWidget):
    """Qt presentation backend preserving the daemon and voice contracts."""

    def __init__(self, start_polling: bool = True) -> None:
        self.app = QApplication.instance() or QApplication([])
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(150, 200)
        screen = self.app.primaryScreen().availableGeometry()
        self.setGeometry(screen.right() - INITIAL_WIDTH - 20, screen.top() + 140, INITIAL_WIDTH, INITIAL_HEIGHT)
        self.daemon_instance_id = os.environ.get("BRAIN_VOICE_DAEMON_INSTANCE_ID", "")
        self.last_seen = time.monotonic()
        self.state = ""
        self.emotion = ""
        self.current_asset = ""
        self._drag_pointer: QPoint | None = None
        self._drag_origin: QPoint | None = None
        self._resize_origin: tuple[str, QPoint, QRect] | None = None
        self.current_display_text = ""
        self.current_message_id = ""
        self.current_codex_thread_id = ""
        self.dismissed_display_text = ""
        self.dismissed_message_id = ""
        self.last_display_text = ""
        self.last_display_emotion = ""
        self.last_consumer_path = ""
        self.last_codex_thread_id = ""
        self.history_count = 1
        self.history_browsing = False
        self.history_anchor_message_id = ""
        self.message_reveal_latched = False
        self.click_count, self.last_click_at = 0, 0.0
        self.reaction_bag = ReactionPhraseBag()
        self.awaiting_quota_animation = ""
        self.last_quota_remaining: tuple[int, int] | None = None
        self._applied_topmost = True

        self.avatar = QLabel(self)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.avatar.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.avatar.setScaledContents(False)
        self.movie: QMovie | None = None

        self.bubble = QtMarkdownBubble()
        self.bubble.geometryChanged.connect(self._update_tail)
        self.bubble.dismissed.connect(self._dismiss_bubble)
        self.bubble.navigateRequested.connect(self._navigate_message)
        self.bubble.replyRequested.connect(self._open_reply_composer)
        self.reply_controller = AvatarReplyController(
            AvatarReplyService(NativeOutboxGateway(AvatarMessageStore()))
        )
        self.reply_window = QtReplyWindow(self.reply_controller)
        self.bubble_hide_timer = QTimer(self)
        self.bubble_hide_timer.setSingleShot(True)
        self.bubble_hide_timer.setInterval(850)
        self.bubble_hide_timer.timeout.connect(self._hide_bubble)
        self.controls = QtAvatarControls(
            self, self._toggle_playback, lambda: self._post("/mute"), self._toggle_pin,
            self._avatar_click, self._refresh_quotas, self._toggle_last_message,
        )
        self.controls.setAccessibleName("Controles del avatar")
        self.controls.hide()
        self.quota_client = CodexQuotaClient()
        self.quota_results: queue.Queue = queue.Queue(maxsize=1)
        self.quota_refreshing = False
        self.hover_timer = QTimer(self)
        self.hover_timer.setInterval(80)
        self.hover_timer.timeout.connect(self._sync_hover)
        self.hover_timer.start()
        self.tail_timer = QTimer(self)
        self.tail_timer.setInterval(33)
        self.tail_timer.timeout.connect(self._refresh_tail)
        self.tail_timer.start()

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(POLL_INTERVAL_MS)
        self.poll_timer.timeout.connect(self._poll)
        if start_polling:
            self.poll_timer.start()
        self.quota_timer = QTimer(self)
        self.quota_timer.setInterval(60_000)
        self.quota_timer.timeout.connect(self._refresh_quotas)
        self.quota_result_timer = QTimer(self)
        self.quota_result_timer.setInterval(250)
        self.quota_result_timer.timeout.connect(self._consume_quota_result)
        if start_polling:
            self.quota_timer.start()
            self.quota_result_timer.start()
            self._refresh_quotas()
        self._set_state("awaiting", force=True)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self.avatar.setGeometry(self.rect())
        self.controls.setGeometry(self.rect())
        self.controls.raise_()
        self._render_movie_frame()
        self._reposition_bubble()

    def moveEvent(self, event) -> None:  # noqa: N802 - Qt API
        """Keep a visible dialogue attached after every native avatar move."""
        super().moveEvent(event)
        self._reposition_bubble()

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.controls.show()
        self.controls.raise_()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().leaveEvent(event)

    def _sync_hover(self) -> None:
        pointer = QCursor.pos()
        visible = self.frameGeometry().contains(pointer)
        self.controls.setVisible(visible)
        if visible:
            self.controls.sync_pointer(pointer)
            self.controls.raise_()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pointer = event.globalPosition().toPoint()
            self._drag_origin = self.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._drag_pointer is not None and self._drag_origin is not None:
            self.move(self._drag_origin + event.globalPosition().toPoint() - self._drag_pointer)
            self._update_tail()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._drag_pointer = None
        self._drag_origin = None
        super().mouseReleaseEvent(event)

    def _post(self, path: str) -> None:
        request = Request(f"{VOICE_DAEMON_URL}{path}", data=b"{}", method="POST", headers={"Content-Type": "application/json"})
        try:
            urlopen(request, timeout=.5).close()
        except OSError:
            pass

    def _toggle_pin(self, checked: bool) -> None:
        self.controls.pinned = checked
        self._apply_topmost()

    def _apply_topmost(self) -> None:
        topmost = self.controls.pinned or self.state in {"preparing", "speaking"}
        if topmost == self._applied_topmost:
            return
        self._applied_topmost = topmost
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, topmost)
        self.bubble.set_pinned(topmost)
        self.show()

    def _toggle_playback(self) -> None:
        self._post("/pause" if self.state in {"muted_replay", "preparing", "speaking"} else "/replay")

    def _avatar_click(self) -> None:
        if self.state in {"preparing", "speaking"}:
            return
        now = time.monotonic()
        self.click_count = self.click_count + 1 if now - self.last_click_at <= 2.0 else 1
        self.last_click_at = now
        if self.click_count < 2:
            return
        self.click_count = 0
        phrase = self.reaction_bag.draw()
        payload = json.dumps({"text": phrase, "lang": "es", "emotion": "reacting", "preludeSeconds": 1}).encode("utf-8")
        request = Request(f"{VOICE_DAEMON_URL}/speak", data=payload, method="POST", headers={"Content-Type": "application/json"})
        try:
            urlopen(request, timeout=.5).close()
        except OSError:
            pass

    def _animation_for_state(self, state: str, emotion: str) -> tuple[str, str]:
        if state in {"preparing", "speaking"}:
            return emotion or "speaking", "speaking"
        if state == "working":
            return "working", "awaiting"
        if state in {"awaiting", "thinking", "muted", "muted_replay"}:
            return self.awaiting_quota_animation or "awaiting", "awaiting"
        return state, "speaking"

    def _set_state(self, state: str, force: bool = False, emotion: str = "") -> None:
        changed = state != self.state or emotion != self.emotion
        self.state, self.emotion = state, emotion
        if state in {"preparing", "speaking"}:
            self.show()
        self._apply_topmost()
        animation, fallback = self._animation_for_state(state, emotion)
        path = avatar_asset(animation, fallback_state=fallback)
        if (changed or force) and path.is_file() and str(path) != self.current_asset:
            if self.movie:
                self.movie.stop()
            self.movie = QMovie(str(path))
            self.movie.setCacheMode(QMovie.CacheMode.CacheNone)
            self.movie.frameChanged.connect(self._render_movie_frame)
            self.movie.start()
            self.current_asset = str(path)
        self.controls.set_state(state in {"muted_replay", "preparing", "speaking"}, self.controls.muted)

    def _set_text(
        self,
        text: str,
        emotion: str = "",
        message_id: str = "",
        consumer_path: str = "",
        history_count: int = 1,
        codex_thread_id: str = "",
    ) -> None:
        incoming_message = bool(message_id and message_id != self.current_message_id)
        if incoming_message:
            self.history_browsing = False
            self.message_reveal_latched = False
            self.dismissed_display_text = ""
            self.dismissed_message_id = ""
        if not text:
            if self.message_reveal_latched:
                return
            self.current_display_text = ""
            self.current_message_id = ""
            self.current_codex_thread_id = ""
            self.dismissed_display_text = ""
            self.dismissed_message_id = ""
            if self.bubble.isVisible() and not self.bubble_hide_timer.isActive():
                self.bubble_hide_timer.start()
            return
        if incoming_message or text != self.current_display_text:
            self.message_reveal_latched = False
        self.last_display_text = text
        self.last_display_emotion = emotion
        self.last_consumer_path = consumer_path
        self.last_codex_thread_id = codex_thread_id
        self.history_count = max(1, history_count)
        previous = self.current_display_text
        previous_message_id = self.current_message_id
        self.current_display_text = text
        self.current_message_id = message_id
        self.current_codex_thread_id = codex_thread_id
        if text == self.dismissed_display_text and message_id == self.dismissed_message_id:
            return
        if text == previous and message_id == previous_message_id and self.bubble.isVisible():
            return
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
        self.bubble.set_reply_available(bool(codex_thread_id))
        if not was_visible:
            self._reposition_bubble(force=True)
        else:
            self._update_tail()
        self.bubble.show()
        self.bubble.raise_()
        self.controls.show()
        self.controls.raise_()

    def _toggle_last_message(self) -> None:
        """Toggle retained visual content without replaying or synthesizing."""
        if self.bubble.isVisible():
            self._dismiss_bubble()
            return
        if not self.last_display_text:
            return
        self.dismissed_display_text = ""
        self.dismissed_message_id = ""
        self.current_display_text = self.last_display_text
        self.message_reveal_latched = True
        self.bubble_hide_timer.stop()
        self.bubble.set_message(
            self.last_display_text,
            emotion_emoji(self.last_display_emotion),
            self.last_consumer_path,
            history_index=0,
            history_total=self.history_count,
        )
        self.current_codex_thread_id = self.last_codex_thread_id
        self.bubble.set_reply_available(bool(self.current_codex_thread_id))
        self._reposition_bubble(force=True)
        self.bubble.show()
        self.bubble.raise_()

    def _message_history(self) -> list[dict]:
        """Read emitted speaks without replaying or mutating daemon state."""
        try:
            with urlopen(f"{VOICE_DAEMON_URL}/messages", timeout=.5) as response:
                payload = json.loads(response.read())
        except Exception:
            return []
        return [item for item in payload.get("speaks", []) if item.get("displayText") or item.get("text")]

    def _navigate_message(self, direction: int) -> None:
        """Browse retained display messages while leaving audio untouched."""
        history = self._message_history()
        if not history:
            return
        current_index = next(
            (index for index, item in enumerate(history) if item.get("id") == self.current_message_id),
            0,
        )
        target_index = current_index + 1 if direction < 0 else current_index - 1
        target_index = max(0, min(target_index, len(history) - 1))
        item = history[target_index]
        self.current_display_text = item.get("displayText") or item.get("text", "")
        self.current_message_id = str(item.get("id", ""))
        self.current_codex_thread_id = str(item.get("codexThreadId", ""))
        self.message_reveal_latched = True
        self.history_browsing = target_index > 0
        self.history_anchor_message_id = str(history[0].get("id", ""))
        self.bubble_hide_timer.stop()
        self._set_bubble_message_anchored(
            self.current_display_text,
            emotion_emoji(str(item.get("emotion", ""))),
            str(item.get("consumerPath", "")),
            history_index=target_index,
            history_total=len(history),
        )
        self.bubble.set_reply_available(bool(self.current_codex_thread_id))
        self.bubble.show()
        self.bubble.raise_()

    def _set_bubble_message_anchored(self, *args, **kwargs) -> None:
        """Resize content along the free vertical side without changing placement."""
        was_visible = self.bubble.isVisible()
        old_position = QPoint(self.bubble.pos())
        old_bottom = self.bubble.geometry().bottom()
        anchored_above = was_visible and self._bubble_is_above_avatar()
        if was_visible:
            self.bubble.set_vertical_placement(anchored_above)
        self.bubble.set_message(*args, **kwargs)
        if not was_visible:
            return
        if anchored_above:
            self.bubble.move(old_position.x(), old_bottom - self.bubble.height() + 1)
        else:
            self.bubble.move(old_position)
        self._update_tail()

    def _open_reply_composer(self) -> None:
        """Open a detached composer bound to the currently displayed speak."""
        if not self.current_codex_thread_id:
            return
        try:
            target = CodexThreadTargetDTO(
                thread_id=self.current_codex_thread_id,
                source_message_id=self.current_message_id,
            )
        except ValueError:
            self.bubble.set_reply_available(False)
            return
        self.reply_window.open_for(target)
        bubble = self.bubble.frameGeometry()
        self.reply_window.setGeometry(bubble)
        self.reply_window.raise_()

    def _bubble_is_above_avatar(self) -> bool:
        """Resolve vertical orientation solely from the current global window centers."""
        return self.bubble.frameGeometry().center().y() < self.frameGeometry().center().y()

    def _dismiss_bubble(self) -> None:
        self.message_reveal_latched = False
        self.dismissed_display_text = self.current_display_text
        self.dismissed_message_id = self.current_message_id
        self.bubble_hide_timer.stop()
        self.bubble.hide()

    def _hide_bubble(self) -> None:
        if self.message_reveal_latched:
            return
        self.bubble.hide()
        if not self.underMouse():
            self.controls.hide()

    def _refresh_quotas(self) -> None:
        if self.quota_refreshing:
            return
        self.quota_refreshing = True
        def worker() -> None:
            snapshot = self.quota_client.read()
            while not self.quota_results.empty():
                try:
                    self.quota_results.get_nowait()
                except queue.Empty:
                    break
            self.quota_results.put(snapshot)
        threading.Thread(target=worker, daemon=True, name="qt-avatar-quota").start()

    def _consume_quota_result(self) -> None:
        try:
            snapshot = self.quota_results.get_nowait()
        except queue.Empty:
            return
        self.quota_refreshing = False
        if snapshot is None:
            return
        self.controls.set_quotas(
            snapshot.five_hour_percent,
            snapshot.weekly_percent,
            quota_reset_label(snapshot.five_hour_resets_at, False),
            quota_reset_label(snapshot.weekly_resets_at, True),
        )
        self.last_quota_remaining = (100 - snapshot.five_hour_percent, 100 - snapshot.weekly_percent)
        next_animation = "sad" if snapshot.weekly_percent >= 90 else "tired" if snapshot.five_hour_percent >= 90 else ""
        if next_animation != self.awaiting_quota_animation:
            self.awaiting_quota_animation = next_animation
            if self.state == "awaiting":
                self._set_state("awaiting", force=True)

    def _render_movie_frame(self, *_args) -> None:
        if self.movie:
            available = QSize(max(1, self.width()), max(1, self.height() - 36))
            self.avatar.setPixmap(fit_avatar_frame(self.movie.currentPixmap(), available))

    def _update_tail(self) -> None:
        self.bubble.set_tail_target(self.mapToGlobal(self.rect().center()))

    def _reposition_bubble(self, force: bool = False) -> None:
        """Attach the bubble to the avatar using the best available screen edge."""
        if not force and (not hasattr(self, "bubble") or not self.bubble.isVisible()):
            return
        screen = self.app.screenAt(self.frameGeometry().center()) or self.app.primaryScreen()
        if screen is None:
            return
        target = bubble_position(screen.availableGeometry(), self.frameGeometry(), self.bubble.size())
        if self.bubble.pos() != target:
            self.bubble.move(target)
        self.bubble.set_vertical_placement(self._bubble_is_above_avatar())
        self._update_tail()

    def _refresh_tail(self) -> None:
        if self.bubble.isVisible():
            self._update_tail()

    def _poll(self) -> None:
        try:
            with urlopen(f"{VOICE_DAEMON_URL}/status", timeout=.2) as response:
                payload = json.loads(response.read())
        except Exception:
            if time.monotonic() - self.last_seen >= DAEMON_LOSS_GRACE_SECONDS:
                self.close()
            return
        if self.daemon_instance_id and payload.get("instanceId") != self.daemon_instance_id:
            self.close()
            return
        self.last_seen = time.monotonic()
        state = payload.get("state", "awaiting")
        emotion = payload.get("emotion", "") or ("happy" if state == "speaking" else "")
        active_message_id = str(payload.get("activeSpeakId", ""))
        self.controls.set_state(state in {"muted_replay", "preparing", "speaking"}, bool(payload.get("muted")))
        self._set_state(state, emotion=emotion)
        if self.history_browsing and (not active_message_id or active_message_id == self.history_anchor_message_id):
            return
        if self.history_browsing:
            self.history_browsing = False
        self._set_text(
            payload.get("displayText", payload.get("text", "")),
            emotion=emotion,
            message_id=active_message_id,
            consumer_path=str(payload.get("activeConsumerPath", "")),
            history_count=int(payload.get("historyCount", 1)),
            codex_thread_id=str(payload.get("activeCodexThreadId", "")),
        )

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.poll_timer.stop()
        self.quota_timer.stop()
        self.quota_result_timer.stop()
        self.hover_timer.stop()
        self.tail_timer.stop()
        self.quota_client.close()
        if self.movie:
            self.movie.stop()
        self.bubble.close()
        self.reply_window.close()
        super().closeEvent(event)

    def run(self) -> int:
        self.show()
        return self.app.exec()
