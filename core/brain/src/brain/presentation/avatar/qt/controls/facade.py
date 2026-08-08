# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Qt avatar control-zone composition facade."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, QRect, QTimer, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from brain.presentation.avatar.qt.controls.bottom import QtBottomControlsMixin
from brain.presentation.avatar.qt.controls.center import QtCenterControlsMixin
from brain.presentation.avatar.qt.controls.geometry import (
    backlog_geometry,
    capture_geometry,
    chrome_geometry,
    mute_geometry,
    pin_fill_color,
    playback_geometry,
    quota_color,
    quota_geometry,
)
from brain.presentation.avatar.qt.controls.top import QtTopControlsMixin


class QtAvatarControls(
    QtCenterControlsMixin, QtTopControlsMixin, QtBottomControlsMixin, QWidget,
):
    """Qt avatar control-zone composition facade managing overlays, buttons, and interactions."""

    def __init__(
        self,
        parent: QWidget,
        on_playback: Callable[[], None],
        on_mute: Callable[[], None],
        on_pin: Callable[[bool], None],
        on_avatar: Callable[[], None],
        on_quota: Callable[[], None],
        on_show_message: Callable[[], None],
        on_cancel_processing: Callable[[], None],
        on_backlog: Callable[[], None],
        on_capture: Callable[[], None],
    ) -> None:
        """Initialize avatar control overlay with action callbacks.

        Args:
            parent (QWidget): Owning parent widget.
            on_playback (Callable[[], None]): Playback toggle handler callback.
            on_mute (Callable[[], None]): Mute toggle handler callback.
            on_pin (Callable[[bool], None]): Window pin toggle handler callback.
            on_avatar (Callable[[], None]): Avatar body click handler callback.
            on_quota (Callable[[], None]): Quota meter click handler callback.
            on_show_message (Callable[[], None]): Message reveal button handler callback.
            on_cancel_processing (Callable[[], None]): Processing cancellation handler callback.
            on_backlog (Callable[[], None]): Backlog window reveal handler callback.
            on_capture (Callable[[], None]): Capture handler; it may no-op when capture is unavailable.

        Returns:
            None.
        """
        super().__init__(parent)
        self.on_playback = on_playback
        self.on_mute = on_mute
        self.on_pin = on_pin
        self.on_avatar = on_avatar
        self.on_quota = on_quota
        self.on_show_message = on_show_message
        self.on_cancel_processing = on_cancel_processing
        self.on_backlog = on_backlog
        self.on_capture = on_capture
        self.expanded = False
        self.playing = False
        self.mute_mode = "off"
        self.muted = False
        self.queue_depth = 0
        self.processing = False
        self.processing_frame = 0
        self.processing_emotion = ""
        self.processing_timer = QTimer(self)
        self.processing_timer.setInterval(50)
        self.processing_timer.timeout.connect(self._advance_processing_animation)
        self.pinned = True
        self.quotas: tuple[int, int] | None = None
        self.quota_resets: tuple[str, str] = ("", "")
        self.quota_refreshing = False
        self.quota_blink_visible = True
        self.quota_blink_timer = QTimer(self)
        self.quota_blink_timer.setInterval(350)
        self.quota_blink_timer.timeout.connect(self._toggle_quota_blink)
        self._hover_corner = ""
        self._resize_origin: tuple[str, QPoint, QRect] | None = None
        self._drag_origin: tuple[QPoint, QPoint] | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)


    def set_state(self, playing: bool, mute_mode: str | bool) -> None:
        """Update playback and three-level mute presentation state.

        Args:
            playing: Whether sequential playback currently owns the audio channel.
            mute_mode: Canonical `off`, `partial`, or `total` mode. Boolean input
                remains accepted for presentation-backend compatibility.
        """
        normalized_mode = "total" if mute_mode is True else "off" if mute_mode is False else str(mute_mode)
        self.playing = playing
        self.mute_mode = normalized_mode if normalized_mode in {"off", "partial", "total"} else "off"
        self.muted = self.mute_mode != "off"
        self.update()

    def set_expanded(self, expanded: bool) -> None:
        """Show full controls on hover or passive status indicators otherwise.

        Args:
            expanded: Whether pointer hover enables the complete interactive chrome.
        """
        self.expanded = expanded
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, not (expanded or self.processing))
        self._refresh_overlay_visibility()

    def _refresh_overlay_visibility(self) -> None:
        """Keep passive queue and processing indicators visible outside hover."""
        self.setVisible(self.expanded or self.processing or self.queue_depth > 0)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, not (self.expanded or self.processing))
        self.update()

    def set_processing(self, processing: bool, emotion: str = "") -> None:
        """Toggle the animated synthesis indicator above the avatar.

        Args:
            processing: Whether thinking or audio preparation is active.
            emotion: Active speak emotion shown inside the processing orbit.
        """
        normalized_emotion = emotion.strip().lower() if processing else ""
        if processing == self.processing and normalized_emotion == self.processing_emotion:
            return
        state_changed = processing != self.processing
        self.processing = processing
        self.processing_emotion = normalized_emotion
        if state_changed:
            self.processing_frame = 0
        if processing:
            self.processing_timer.start()
        else:
            self.processing_timer.stop()
        self._refresh_overlay_visibility()

    def _advance_processing_animation(self) -> None:
        """Advance one rotation and pulse frame for the processing dots."""
        self.processing_frame = (self.processing_frame + 1) % 360
        self.update()

    def set_queue_depth(self, queue_depth: int) -> None:
        """Update the pending voice-item badge rendered over the message control.

        Args:
            queue_depth: Number of voice requests waiting for sequential presentation.
        """
        normalized_depth = max(0, queue_depth)
        if normalized_depth == self.queue_depth:
            return
        self.queue_depth = normalized_depth
        self._refresh_overlay_visibility()

    def set_quotas(self, five_hour: int, weekly: int, five_reset: str = "", weekly_reset: str = "") -> None:
        """Update five-hour and weekly quota values.

        Args:
            five_hour (int): Consumed five-hour quota percentage.
            weekly (int): Consumed weekly quota percentage.
            five_reset (str): Display label for five-hour reset.
            weekly_reset (str): Display label for weekly reset.
        """
        self.quotas = (five_hour, weekly)
        self.quota_resets = (five_reset, weekly_reset)
        self.update()

    def set_quota_refreshing(self, refreshing: bool) -> None:
        """Blink both quota meters while a manual or scheduled refresh runs.

        Args:
            refreshing: Whether a quota request is currently in flight.
        """
        if refreshing == self.quota_refreshing:
            return
        self.quota_refreshing = refreshing
        self.quota_blink_visible = True
        if refreshing:
            self.quota_blink_timer.start()
        else:
            self.quota_blink_timer.stop()
        self.update()

    def _toggle_quota_blink(self) -> None:
        """Alternate quota visibility to signal an active refresh."""
        self.quota_blink_visible = not self.quota_blink_visible
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        """Paint full hover chrome or persistent passive indicators.

        Args:
            event (object): Qt paint event.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_processing(painter)
        if self.expanded:
            self._paint_quotas(painter)
            self._paint_playback(painter)
            self._paint_mute(painter)
            self._paint_pin(painter)
            self._paint_show_message(painter)
            self._paint_backlog(painter)
            self._paint_capture(painter)
            self._paint_resize_grip(painter)
        elif self.queue_depth:
            self._paint_passive_queue(painter)
        painter.end()
