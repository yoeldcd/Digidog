# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Qt avatar runtime, controls, processing, quota, and history tests."""
import json
import os
from types import SimpleNamespace
from unittest.mock import call, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPixmap
from PySide6.QtTest import QTest

from brain.presentation.avatar.window.backend import requested_avatar_backend, resolve_avatar_window_class
from brain.presentation.avatar.interactivity.markdown_document import (
    avatar_markdown_source,
    expand_avatar_images,
    normalize_avatar_markdown,
    render_embedded_file_blocks,
)
from brain.presentation.avatar.interactivity.reactions import AvatarReactionDTO, ReactionPhraseBag
from brain.presentation.avatar.qt.bubble import (
    QtMarkdownBubble,
    normalized_image_size,
    semantic_token_ranges,
    table_column_percentages,
)
from brain.presentation.avatar.qt.runtime import (
    QtAvatarWindow,
    bubble_position,
    bubble_vertical_lane,
    fit_avatar_frame,
    quota_reset_label,
    reply_composer_geometry,
)
from brain.presentation.avatar.tk.avatar.window import AvatarWindow


def test_show_message_reopens_last_visual_without_voice_request() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_text("Último mensaje visual", "happy")
    window.bubble._dismiss()
    assert not window.bubble.isVisible()
    with patch.object(window, "_post") as post:
        window._toggle_last_message()
    assert window.bubble.isVisible()
    assert "Último mensaje visual" in window.bubble.document_view.toPlainText()
    post.assert_not_called()
    window._set_text("", "")
    window._hide_bubble()
    assert window.bubble.isVisible()
    window.bubble._dismiss()
    assert not window.message_reveal_latched
    assert not window.bubble.isVisible()
    window.close()

def test_queue_badge_remains_visible_as_passive_click_through_chrome() -> None:
    """Queued work survives hover exit without exposing unrelated controls."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    controls = window.controls
    window.show()
    app.processEvents()
    controls.set_expanded(False)
    controls.set_queue_depth(1)
    assert controls.isVisible()
    assert controls.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    controls.set_queue_depth(0)
    assert not controls.isVisible()
    window.close()

def test_processing_dots_remain_visible_without_pointer_hover() -> None:
    """Thinking and preparation own passive visibility until work completes."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    controls = window.controls
    window.show()
    app.processEvents()
    controls.set_expanded(False)
    controls.set_processing(True)
    assert controls.isVisible()
    assert not controls.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    controls.set_processing(False)
    assert not controls.isVisible()
    window.close()

def test_mute_icon_distinguishes_partial_slash_from_total_cross() -> None:
    """Mute chrome maps partial to one slash and total to two crossing lines."""
    import inspect

    from brain.presentation.avatar.qt.controls import QtAvatarControls

    source = inspect.getsource(QtAvatarControls._paint_mute)
    assert 'if self.mute_mode != "off"' in source
    assert 'if self.mute_mode == "total"' in source
    assert source.count("painter.drawLine(") == 2

def test_processing_indicator_tracks_daemon_processing_not_runtime_labels() -> None:
    """Thinking alone is idle chrome; only explicit daemon processing animates dots."""
    import inspect

    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window._set_state("thinking")
    assert window.controls.processing is False
    assert not window.controls.processing_timer.isActive()
    window._set_state("thinking", processing=True, processing_emotion="focused")
    assert window.controls.processing is True
    assert window.controls.processing_timer.isActive()
    window._set_state("awaiting", processing=False)
    assert window.controls.processing is False
    assert not window.controls.processing_timer.isActive()
    poll_source = inspect.getsource(QtAvatarWindow._poll)
    assert "presentation.processing_indicator_active" in poll_source
    assert "presentation.speaking_animation_active" in poll_source
    window.close()

def test_processing_indicator_reuses_explorer_working_palette() -> None:
    """Qt presents the same six semantic dot colors used by Brain Explorer."""
    import inspect

    from brain.presentation.avatar.qt.controls import QtAvatarControls

    source = inspect.getsource(QtAvatarControls._paint_processing)
    center_source = inspect.getsource(QtAvatarControls._processing_center)
    for color in ("#3b82f6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#ec4899"):
        assert color in source
    assert "message_bounds.center()" in center_source

def test_message_icon_fills_white_and_centers_red_buffer_count() -> None:
    """The queue depth is text inside the bubble, never a detached badge circle."""
    import inspect

    from brain.presentation.avatar.qt.controls import QtAvatarControls

    source = inspect.getsource(QtAvatarControls._paint_show_message)
    assert 'painter.setBrush(QColor("#ffffff"))' in source
    assert 'painter.setPen(QColor("#e32636"))' in source
    assert "painter.drawText(bubble_bounds, Qt.AlignmentFlag.AlignCenter, buffer_text)" in source
    assert 'buffer_text = "99+" if self.queue_depth > 99' in source
    facade_source = inspect.getsource(QtAvatarControls.paintEvent)
    assert "elif self.queue_depth:" in facade_source
    assert "self._paint_passive_queue(painter)" in facade_source
    assert "drawEllipse" not in source


def test_t716_clock_and_passive_queue_use_distinct_visual_layers() -> None:
    """Keep the clock palette and passive queue free of the bubble body."""
    import inspect

    from brain.presentation.avatar.qt.controls import QtAvatarControls

    clock_source = inspect.getsource(QtAvatarControls._paint_backlog)
    passive_source = inspect.getsource(QtAvatarControls._paint_passive_queue)

    assert 'painter.setBrush(QColor("#ffffff"))' in clock_source
    assert "painter.setPen(Qt.PenStyle.NoPen)" in clock_source
    assert 'QColor("#123b78")' in clock_source
    assert "drawRoundedRect" not in passive_source
    assert "drawPath" not in passive_source
    assert 'painter.setPen(QColor("#e32636"))' in passive_source


def test_action_chrome_paints_icons_without_opaque_square_backgrounds() -> None:
    """Visual transparency does not alter the square hitbox geometry."""
    import inspect

    from brain.presentation.avatar.qt.controls import QtAvatarControls, chrome_geometry

    for method in (
        QtAvatarControls._paint_pin,
        QtAvatarControls._paint_show_message,
        QtAvatarControls._paint_resize_grip,
    ):
        source = inspect.getsource(method)
        assert "fillRect(bounds" not in source
        assert "drawRect(bounds" not in source
    pin, message, grip = chrome_geometry(300, 400)
    assert pin.width() == pin.height()
    assert message.width() == message.height()
    assert grip.width() == grip.height()

def test_quota_refresh_blinks_until_the_result_is_consumed() -> None:
    """Manual and automatic quota reads expose the same visible busy state."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    with patch.object(window.quota_client, "read", return_value=None):
        window._refresh_quotas()
        assert window.controls.quota_refreshing is True
        assert window.controls.quota_blink_timer.isActive()
        window.quota_results.get(timeout=1)
        window.quota_results.put(None)
        window._consume_quota_result()
    assert window.controls.quota_refreshing is False
    assert not window.controls.quota_blink_timer.isActive()
    window.close()

def test_clicking_either_quota_meter_requests_refresh() -> None:
    """Both circular quota hitboxes retain click-to-refresh behavior."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.resize(300, 400)
    window.controls.resize(window.size())
    window.controls.show()
    with patch.object(window.controls, "on_quota") as refresh:
        left, right, _radius = __import__(
            "brain.presentation.avatar.qt.controls", fromlist=["quota_geometry"]
        ).quota_geometry(window.width(), window.height())
        QTest.mouseClick(window.controls, Qt.MouseButton.LeftButton, pos=left.toPoint())
        QTest.mouseClick(window.controls, Qt.MouseButton.LeftButton, pos=right.toPoint())
    assert refresh.call_count == 2
    window.close()

def test_history_navigation_changes_visual_only_and_preserves_provenance() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    history = [
        {"id": "new", "displayText": "Nuevo", "emotion": "happy", "consumerPath": r"D:\new"},
        {
            "id": "old",
            "displayText": "\n\n".join(f"Párrafo histórico {index} con contenido legible." for index in range(12)),
            "emotion": "focused",
            "consumerPath": r"D:\old",
        },
    ]
    window.show()
    window._set_text("Nuevo", "happy", "new", r"D:\new", 2)
    short_height = window.bubble.height()
    # The windows may overlap vertically while the bubble is still relatively above.
    # Orientation must follow their real centers, not a strict edge-gap threshold.
    window.bubble.move(window.x(), window.frameGeometry().center().y() - short_height)
    window.bubble.set_vertical_placement(True)
    assert window._bubble_is_above_avatar()
    assert window.bubble.geometry().bottom() > window.frameGeometry().top()
    anchored_bottom = window.bubble.geometry().bottom()
    anchored_x = window.bubble.x()
    with patch.object(window, "_message_history", return_value=history), patch.object(window, "_post") as post:
        window._navigate_message(-1)
        assert "Párrafo histórico 0" in window.bubble.document_view.toPlainText()
        assert window.bubble.history_label.text() == "1/2"
        assert window.bubble.source_label.toolTip() == r"D:\old"
        assert window.bubble.x() == anchored_x
        assert window.bubble.geometry().bottom() == anchored_bottom
        assert window.bubble.layout().indexOf(window.bubble.footer) == 4
        assert short_height < window.bubble.height() <= window.bubble.maximumHeight()
        window._navigate_message(1)
    assert "Nuevo" in window.bubble.document_view.toPlainText()
    assert window.bubble.x() == anchored_x
    assert window.bubble.geometry().bottom() == anchored_bottom
    post.assert_not_called()
    window.close()

def test_history_numbering_is_chronological_over_newest_first_storage() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    initial_history = [
        {"id": "second", "displayText": "Segundo"},
        {"id": "first", "displayText": "Primero"},
    ]
    window._set_text("Segundo", message_id="second", history_count=2)
    assert window.bubble.history_label.text() == "2/2"

    expanded_history = [
        {"id": "third", "displayText": "Tercero"},
        *initial_history,
    ]
    window._set_text("Tercero", message_id="third", history_count=3)
    assert window.bubble.history_label.text() == "3/3"

    with patch.object(window, "_message_history", return_value=expanded_history):
        window._navigate_message(-1)
        assert window.current_message_id == "second"
        assert window.bubble.history_label.text() == "2/3"
        assert window.bubble.backward_button.isEnabled()
        assert window.bubble.forward_button.isEnabled()
        window._navigate_message(1)

    assert window.current_message_id == "third"
    assert window.bubble.history_label.text() == "3/3"
    assert window.bubble.backward_button.isEnabled()
    assert not window.bubble.forward_button.isEnabled()
    window.close()

def test_open_history_stays_visually_pinned_until_explicitly_closed() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    history = [
        {"id": "new", "displayText": "Nuevo", "emotion": "happy"},
        {"id": "old", "displayText": "Histórico fijado", "emotion": "focused"},
    ]
    window.show()
    window._set_text("Nuevo", "happy", "new", history_count=2)
    with patch.object(window, "_message_history", return_value=history):
        window._navigate_message(-1)

    window._set_text("Mensaje hablado entrante", "happy", "active-two", history_count=3)
    window._set_text("[Narrativa no hablada]", "focused", history_count=3)
    assert window.history_browsing is True
    assert window.current_message_id == "old"
    assert window.bubble.document_view.toPlainText().strip() == "Histórico fijado"
    assert window.last_display_text == "[Narrativa no hablada]"

    window.state = "muted"
    with patch.object(window, "_post") as post:
        window._dismiss_bubble()
    post.assert_not_called()
    assert window.history_browsing is False
    assert not window.bubble.isVisible()

    window._set_text("Mensaje hablado entrante", "happy", "active-two", history_count=3)
    assert "Mensaje hablado entrante" in window.bubble.document_view.toPlainText()
    window.close()
    app.processEvents()

def test_qt_pin_priority_is_synchronized_with_bubble() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window._set_text("Mensaje visible", "happy")
    window.state = "speaking"
    window._toggle_pin(False)
    assert not bool(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
    assert not bool(window.bubble.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
    window._toggle_pin(True)
    assert bool(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
    assert bool(window.bubble.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
    window.close()
    app.processEvents()

def test_processing_border_wraps_message_icon_without_head_orbit() -> None:
    """Processing animates the message control border instead of dots over the avatar."""
    import inspect

    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    controls = window.controls
    controls.set_processing(True, "focused")

    assert controls.processing_emotion == "focused"
    source = inspect.getsource(controls._paint_processing)
    assert "QConicalGradient" in source
    assert "border_gradient.setColorAt" in source
    assert "self.processing_frame * 8" in source
    assert "4.2 / scale" in source
    assert "bubble.united(tail)" in source
    assert "drawPath(silhouette)" in source
    assert "message_bounds.adjusted" not in source
    assert "orbit_radius" not in source
    controls.set_processing(True, "happy")
    assert controls.processing_frame == 0
    assert controls.processing_emotion == "happy"
    controls.set_processing(False)
    assert controls.processing_emotion == ""
    window.close()
