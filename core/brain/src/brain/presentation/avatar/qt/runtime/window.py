# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Thin PySide6 avatar composition root.

Main execution window for the desktop avatar runtime. Coordinates animated GIF
rendering, speech bubble overlays, quota meters, and asynchronous status polling
with the background voice daemon.
"""

from __future__ import annotations

import os
import queue
import time

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QMovie, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from brain.infrastructure.codex.quota_client import CodexQuotaClient, CodexQuotaSnapshot
from brain.presentation.avatar.qt.reply_window.controller import AvatarReplyController
from brain.presentation.avatar.communication.reply.daemon_gateway import (
    DaemonReplyGateway,
)
from brain.presentation.avatar.qt.reply_window import QtReplyWindow
from brain.presentation.avatar.qt.reply_window.screenshot import (
    QtReplyScreenshotCoordinator,
)
from brain.presentation.avatar.communication.reply.service import AvatarReplyService
from brain.presentation.avatar.interactivity.presentation_state import (
    ProjectedMessageState,
)
from brain.presentation.avatar.interactivity.quota_view_model import (
    quota_reset_label as _shared_quota_reset_label,
)
from brain.presentation.avatar.interactivity.reactions import (
    ReactionPhraseBag,
    load_avatar_interaction_config,
)
from brain.presentation.avatar.qt.avatar.geometry import (
    QtWindowGeometryMixin,
    bubble_position,
    bubble_vertical_lane,
    clamp_bubble_position,
    reply_composer_geometry,
)
from brain.presentation.avatar.qt.avatar.renderer import (
    QtAvatarRendererMixin,
    fit_avatar_frame,
)
from brain.presentation.avatar.qt.backlog.application.composition import (
    create_backlog_window,
)
from brain.presentation.avatar.qt.backlog.annotation.dialog import AnnotationDialog
from brain.presentation.avatar.qt.backlog.presentation.capture import QtScreenCapture
from brain.presentation.avatar.qt.backlog.presentation.window import BacklogWindow
from brain.presentation.avatar.qt.bubble.facade import QtMarkdownBubble
from brain.presentation.avatar.qt.controls.facade import QtAvatarControls
from brain.presentation.avatar.qt.runtime.backend_adapter import QtBackendAdapterMixin
from brain.presentation.avatar.qt.runtime.message_controller import (
    QtMessageControllerMixin,
)
from brain.presentation.avatar.qt.runtime.quota_controller import QtQuotaControllerMixin
from brain.presentation.avatar.window.config import INITIAL_HEIGHT, INITIAL_WIDTH, POLL_INTERVAL_MS


def quota_reset_label(timestamp: int, weekly: bool) -> str:
    """Compatibility wrapper around the shared quota label policy.

    Args:
        timestamp (int): Unix timestamp for the quota reset time.
        weekly (bool): True if checking weekly window reset, False for daily.

    Returns:
        str: Formatted human-readable quota reset label.
    """
    label = _shared_quota_reset_label(timestamp, weekly=weekly)

    return "--" if weekly and not timestamp else label


class QtAvatarWindow(
    QtBackendAdapterMixin,
    QtMessageControllerMixin,
    QtQuotaControllerMixin,
    QtAvatarRendererMixin,
    QtWindowGeometryMixin,
    QWidget,
):
    """Main PySide6 desktop avatar floating window facade."""

    def __init__(self, start_polling: bool = True) -> None:
        """Initialize frameless translucent avatar main window and controllers.

        Args:
            start_polling (bool): Whether daemon polling timers start immediately.

        Returns:
            None.
        """
        self.app = QApplication.instance() or QApplication([])

        # The avatar service owns process lifetime. Auxiliary top-level windows
        # may close without making Qt terminate and the supervisor relaunch us.
        self.app.setQuitOnLastWindowClosed(False)
        window_flags = Qt.WindowType.FramelessWindowHint
        window_flags |= Qt.WindowType.WindowStaysOnTopHint
        window_flags |= Qt.WindowType.Tool
        super().__init__(None, window_flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(150, 200)
        screen = self.app.primaryScreen().availableGeometry()
        initial_size = self.minimumSize()
        window_x = screen.right() - initial_size.width() + 1
        window_y = screen.bottom() - initial_size.height() + 1
        self.setGeometry(window_x, window_y, initial_size.width(), initial_size.height())
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
        self.active_speak_id = ""
        self.active_presentation_owned = False
        self.presentation_state = ProjectedMessageState()
        self.current_audio_name = ""
        self.current_codex_thread_id = ""
        self.current_has_embedded_file = False
        self.current_manual_speech = False
        self.dismissed_display_text = ""
        self.dismissed_message_id = ""
        self.last_display_text = ""
        self.last_message_id = ""
        self.last_display_emotion = ""
        self.last_consumer_path = ""
        self.last_codex_thread_id = ""
        self.last_has_embedded_file = False
        self.last_manual_speech = False
        self.playback_active = False
        self.progressive_playback_active = False
        self.history_count = 1
        self.history_browsing = False
        self.history_anchor_message_id = ""
        self.message_reveal_latched = False
        self.ignore_quota_state, configured_reactions = load_avatar_interaction_config()
        self.reaction_bag = ReactionPhraseBag(reactions=configured_reactions)
        self.avatar_click_timer = QTimer(self)
        self.avatar_click_timer.setSingleShot(True)
        self.avatar_click_timer.setInterval(self.app.doubleClickInterval())
        self.avatar_click_timer.timeout.connect(self._commit_avatar_click)
        self.awaiting_quota_animation = ""
        self.last_quota_remaining: tuple[int, int] | None = None
        self._applied_topmost = True
        self._theme_mode = "dark"
        self._constraining_bubble_drag = False
        self._bubble_manual_position: QPoint | None = None
        self._bubble_manual_bottom: int | None = None
        self._bubble_auto_lane = ""
        self._window_ready_sent = False
        self.backlog_window: BacklogWindow | None = None

        self.avatar = QLabel(self)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.avatar.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.avatar.setScaledContents(False)
        self.movie: QMovie | None = None

        self.bubble = QtMarkdownBubble()
        self.bubble.set_theme(self._theme_mode)
        self.bubble.geometryChanged.connect(self._update_tail)
        self.bubble.geometryChanged.connect(self._constrain_bubble_drag)
        self.bubble.manuallyMoved.connect(self._retain_bubble_offset)
        self.bubble.dismissed.connect(self._dismiss_bubble)
        self.bubble.navigateRequested.connect(self._navigate_message)
        self.bubble.replyRequested.connect(self._open_reply_composer)

        self.reply_controller = AvatarReplyController(
            AvatarReplyService(DaemonReplyGateway())
        )
        self.reply_window = QtReplyWindow(self.reply_controller)
        self.reply_window.set_theme(self._theme_mode)
        self.reply_screenshot_coordinator = QtReplyScreenshotCoordinator(
            self.reply_window,
            QtScreenCapture(),
            self._create_reply_annotation_editor,
        )

        self.bubble_hide_timer = QTimer(self)
        self.bubble_hide_timer.setSingleShot(True)
        self.bubble_hide_timer.setInterval(850)
        self.bubble_hide_timer.timeout.connect(self._hide_bubble)

        self.controls = QtAvatarControls(
            self,
            self._activate_message_control,
            lambda: self._post("/mute"),
            self._toggle_pin,
            self._avatar_click,
            self._refresh_quotas,
            self._toggle_last_message,
            lambda: self._post("/cancel-processing"),
            self._open_backlog_window,
            self._open_capture_form,
        )
        self.controls.setAccessibleName("Controles del avatar")
        self.controls.hide()

        self.quota_client = CodexQuotaClient()
        self.quota_results: queue.Queue[CodexQuotaSnapshot | None] = queue.Queue(
            maxsize=1
        )
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

        # Conditional check: evaluate domain preconditions and invariants

        if start_polling:
            self.poll_timer.start()

        self.quota_timer = QTimer(self)
        self.quota_timer.setInterval(60_000)
        self.quota_timer.timeout.connect(self._refresh_quotas)
        self.quota_result_timer = QTimer(self)
        self.quota_result_timer.setInterval(250)
        self.quota_result_timer.timeout.connect(self._consume_quota_result)

        # Conditional check: evaluate domain preconditions and invariants

        if start_polling:
            self.quota_timer.start()
            self.quota_result_timer.start()
            self._refresh_quotas()
        self._set_state("awaiting", force=True)

        # Conditional check: evaluate domain preconditions and invariants

        if start_polling:

            # PID registration is not readiness; defer until Qt processes events.
            QTimer.singleShot(0, self._signal_window_ready)

    def _backlog_window_for_action(self) -> BacklogWindow:
        """Return the singleton backlog coordinator without changing visibility.

        Args:
            None.

        Returns:
            BacklogWindow: Existing or newly composed backlog window.
        """

        # Conditional check: evaluate domain preconditions and invariants

        if self.backlog_window is None:
            self.backlog_window = create_backlog_window(
                theme_mode=self._theme_mode,
            )

            return self.backlog_window

        self.backlog_window.reload_projects()

        return self.backlog_window

    def _create_reply_annotation_editor(
        self, pixmap: QPixmap, parent: QWidget | None
    ) -> AnnotationDialog:
        """Build the reused annotation editor with the avatar's active theme.

        Args:
            pixmap: Source-resolution desktop capture to annotate.
            parent: Composer that owns the temporary modeless editor.

        Returns:
            AnnotationDialog: Reused annotation workflow without backlog ownership.
        """

        return AnnotationDialog(pixmap, parent=parent, theme=self._theme_mode)

    def _open_backlog_window(self) -> None:
        """Show and focus the backlog task-list window.

        Args:
            None.

        Returns:
            None.
        """
        backlog = self._backlog_window_for_action()

        # Conditional check: evaluate domain preconditions and invariants

        if hasattr(backlog, "show_backlog_window"):
            backlog.show_backlog_window()

        else:
            backlog.show()
            backlog.raise_()
            backlog.activateWindow()

    def _open_capture_form(self) -> None:
        """Open or reuse the capture form without showing the task list.

        Args:
            None.

        Returns:
            None.
        """
        backlog = self._backlog_window_for_action()
        backlog.hide()
        backlog.open_capture_form()

    def _signal_window_ready(self) -> None:
        """Signal completed GUI setup after Qt processes the ready event.

        Args:
            None.

        Returns:
            None: A readiness notification is posted at most once.
        """

        # Conditional check: evaluate domain preconditions and invariants

        if self._window_ready_sent:

            return
        self._window_ready_sent = True
        self._post("/window-ready", {"pid": os.getpid()})

    def _toggle_pin(self, checked: bool) -> None:
        """Toggle window pinned state and synchronize topmost window priority.

        Args:
            checked (bool): New pin state.

        Returns:
            None.
        """
        self.controls.pinned = checked
        self._apply_topmost()

    def _apply_topmost(self) -> None:
        """Apply window topmost flags when pinned state changes.

        Args:
            None.

        Returns:
            None.
        """
        # The pin is the sole user authority over z-order. Playback must not
        # silently override an explicit unpin while the icon shows it disabled.
        topmost = self.controls.pinned

        # Conditional check: evaluate domain preconditions and invariants

        if topmost == self._applied_topmost:

            return
        self._applied_topmost = topmost
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, topmost)
        self.bubble.set_pinned(topmost)
        self.show()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        """Stop timers and owned resources before closing the Qt window.

        Args:
            event (QCloseEvent): Qt close event.

        Returns:
            None: Timers and owned windows are closed before Qt exits.
        """
        self.poll_timer.stop()
        self.quota_timer.stop()
        self.quota_result_timer.stop()
        self.hover_timer.stop()
        self.tail_timer.stop()
        self.quota_client.close()

        # Conditional check: evaluate domain preconditions and invariants

        if self.movie:
            self.movie.stop()
        self.bubble.close()
        self.reply_screenshot_coordinator.close()
        self.reply_window.close()

        # Conditional check: evaluate domain preconditions and invariants

        if self.backlog_window is not None:
            self.backlog_window.close()
        super().closeEvent(event)

        # Because automatic last-window shutdown is disabled, only closing the
        # avatar root terminates its event loop intentionally.
        self.app.quit()

    def run(self) -> int:
        """Show the avatar and enter its Qt event loop.

        Args:
            None.

        Returns:
            int: Qt application exit status.
        """
        self.show()

        return self.app.exec()
