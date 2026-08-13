# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Qt avatar window, rendering, controls, and resize geometry tests."""
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
from brain.presentation.avatar.qt.avatar.geometry import avoid_avatar_overlap
from brain.presentation.avatar.tk.avatar.window import AvatarWindow


def test_directional_bubble_tail_touches_avatar_boundary() -> None:
    """Bottom avatars anchor upward and top avatars anchor downward by the tail tip."""
    screen = QRect(0, 0, 1200, 900)
    size = QSize(480, 240)
    bottom_avatar = QRect(900, 620, 250, 260)
    above = bubble_position(screen, bottom_avatar, size)
    assert above.y() + size.height() - 5 == bottom_avatar.top()

    top_avatar = QRect(900, 20, 250, 260)
    below = bubble_position(screen, top_avatar, size)
    assert below.y() + 5 == top_avatar.bottom()


def test_avatar_window_initializes_minimum_size_at_bottom_right_in_dark_theme() -> None:
    """Initialize avatar minimum geometry at bottom right with dark surfaces."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    screen = app.primaryScreen()
    assert screen is not None
    available = screen.availableGeometry()

    assert window.size() == window.minimumSize()
    assert window.geometry().right() == available.right()
    assert window.geometry().bottom() == available.bottom()
    assert window._theme_mode == "dark"
    assert window.bubble._theme_mode == "dark"
    assert window.reply_window._theme_mode == "dark"
    window.close()


def test_overlap_projection_selects_nearest_free_avatar_edge() -> None:
    """Project a dragged bubble outside the avatar while preserving intent."""
    viewport = QRect(0, 0, 1200, 800)
    avatar = QRect(900, 550, 200, 240)
    candidate = QRect(820, 500, 300, 220)

    projected = avoid_avatar_overlap(viewport, avatar, candidate)
    result = QRect(projected, candidate.size())

    assert viewport.contains(result)
    assert not result.intersects(avatar)

def test_bubble_zoom_controls_and_footer_actions_follow_avatar_alignment() -> None:
    """Keep zoom bounded and group actions on the avatar-facing footer side."""
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    bubble.set_message("Mensaje de prueba")
    bubble.show()
    app.processEvents()

    QTest.mouseClick(bubble.zoom_in_button, Qt.MouseButton.LeftButton)
    assert bubble._zoom_step == 1
    assert bubble.reply_button.text() == "💭"
    assert bubble.reply_button.accessibleName() == "Responder en Codex"
    assert bubble.footer_layout.indexOf(bubble.reply_button) < bubble.footer_layout.indexOf(bubble.backward_button)
    navigation_center = (bubble.backward_button.x() + bubble.forward_button.geometry().right()) / 2
    assert abs(navigation_center - bubble.footer.width() / 2) <= 4
    assert bubble.footer_layout.indexOf(bubble.remaining_label) > bubble.footer_layout.indexOf(bubble.forward_button)

    bubble.set_tail_target(bubble.mapToGlobal(QPoint(bubble.width(), bubble.height() // 2)))
    assert bubble.footer_layout.indexOf(bubble.reply_button) > bubble.footer_layout.indexOf(bubble.forward_button)
    assert bubble.footer_layout.indexOf(bubble.remaining_label) < bubble.footer_layout.indexOf(bubble.backward_button)
    app.processEvents()
    navigation_center = (bubble.backward_button.x() + bubble.forward_button.geometry().right()) / 2
    assert abs(navigation_center - bubble.footer.width() / 2) <= 4

    for _ in range(8):
        QTest.mouseClick(bubble.zoom_out_button, Qt.MouseButton.LeftButton)
    assert bubble._zoom_step == -3
    assert not bubble.zoom_out_button.isEnabled()
    bubble.close()

def test_qt_avatar_runtime_constructs_without_polling() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    assert window.poll_timer.isActive() is False
    assert window.bubble.document_view.textInteractionFlags()
    assert window.controls.pinned is True
    assert window.controls.accessibleName() == "Controles del avatar"
    window.bubble.set_theme("dark")
    window.reply_window.set_theme("dark")
    assert window.bubble.property("avatarTheme") == "dark"
    assert window.reply_window.property("avatarTheme") == "dark"
    window.controls.set_state(playing=True, mute_mode="total")
    window.controls.set_quotas(25, 60, "14:00", "21 JUL")
    assert window.controls.playing is True
    assert window.controls.muted is True
    assert window.controls.mute_mode == "total"
    assert window.controls.quotas == (25, 60)
    window.close()
    app.processEvents()

def test_frame_fit_preserves_original_canvas_across_different_alpha_bounds() -> None:
    app = QApplication.instance() or QApplication([])
    first = QPixmap(300, 200)
    first.fill(Qt.GlobalColor.transparent)
    from PySide6.QtGui import QPainter
    painter = QPainter(first)
    painter.fillRect(QRect(20, 20, 40, 160), QColor("pink"))
    painter.end()
    second = QPixmap(300, 200)
    second.fill(Qt.GlobalColor.transparent)
    painter = QPainter(second)
    painter.fillRect(QRect(100, 50, 180, 80), QColor("pink"))
    painter.end()
    first_fitted = fit_avatar_frame(first, QSize(240, 400))
    second_fitted = fit_avatar_frame(second, QSize(240, 400))
    assert first_fitted.size() == QSize(240, 160)
    assert second_fitted.size() == first_fitted.size()

def test_avatar_drag_and_both_resize_affordances_are_reachable() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.move(window.x(), 0)
    window.show()
    app.processEvents()
    start = window.pos()
    QTest.mousePress(window.controls, Qt.MouseButton.LeftButton, pos=window.controls.rect().center())
    QTest.mouseMove(window.controls, window.controls.rect().center() + QPoint(35, 25), delay=10)
    QTest.mouseRelease(window.controls, Qt.MouseButton.LeftButton, pos=window.controls.rect().center() + QPoint(35, 25))
    assert window.pos() != start
    window.controls.sync_pointer(window.controls.mapToGlobal(QPoint(window.width() - 4, window.height() - 4)))
    assert window.controls._hover_corner == "se"
    bubble = window.bubble
    assert bubble._resize_corner(bubble._bubble_body_rect().topLeft()) == "nw"
    window.close()

def test_message_below_avatar_grows_downward_from_fixed_top() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.move(window.x(), 0)
    window.show()
    window.bubble.set_vertical_placement(False)
    window.bubble.set_message("Breve")
    window.bubble.move(window.x(), window.frameGeometry().bottom() + 10)
    window.bubble.show()
    app.processEvents()
    fixed_position = QPoint(window.bubble.pos())
    fixed_footer_y = window.bubble.mapToGlobal(window.bubble.footer.pos()).y()
    short_height = window.bubble.height()
    window._set_bubble_message_anchored("\n\n".join(f"Párrafo {index}" for index in range(20)))
    assert window.bubble.pos() == fixed_position
    assert window.bubble.height() > short_height
    assert window.bubble.y() > window.frameGeometry().bottom()
    assert window.bubble.mapToGlobal(window.bubble.footer.pos()).y() == fixed_footer_y
    assert window.bubble.layout().indexOf(window.bubble.footer) == 0
    assert window.bubble.layout().indexOf(window.bubble.header) == 4
    assert window.bubble.close_button.geometry().center().y() == window.bubble.header.geometry().center().y()
    footer_gap = window.bubble.document_view.y() - (
        window.bubble.footer.y() + window.bubble.footer.height()
    )
    header_gap = window.bubble.header.y() - (
        window.bubble.document_view.y() + window.bubble.document_view.height()
    )
    assert footer_gap == header_gap == 10
    window.close()

def test_bubble_follows_avatar_but_preserves_manual_message_geometry() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_text("Mensaje adherido", "happy", "speak-one")
    app.processEvents()
    window.move(window.x() - 180, window.y() + 90)
    app.processEvents()
    screen = app.screenAt(window.frameGeometry().center()) or app.primaryScreen()
    expected = bubble_position(screen.availableGeometry(), window.frameGeometry(), window.bubble.size())
    assert window.bubble.pos() == expected
    window.resize(window.width() + 30, round((window.width() + 30) * 4 / 3))
    app.processEvents()
    expected = bubble_position(screen.availableGeometry(), window.frameGeometry(), window.bubble.size())
    assert window.bubble.pos() == expected
    position_before_message_resize = QPoint(window.bubble.pos())
    window.bubble.resize(window.bubble.width(), min(window.bubble.maximumHeight(), window.bubble.height() + 40))
    app.processEvents()
    assert window.bubble.pos() == position_before_message_resize
    window.bubble.move(0, 0)
    app.processEvents()
    assert window.bubble.pos() == QPoint(0, 0)
    window.close()

def test_manual_bubble_offset_persists_until_avatar_relocation() -> None:
    """Keep a user displacement across content refreshes, then reset on avatar move."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_text('Primero', 'happy', 'one')
    app.processEvents()
    manual_position = window.bubble.pos() + QPoint(28, 20)
    window.bubble.move(manual_position)
    window._retain_bubble_offset()
    manual_position = QPoint(window.bubble.pos())
    window.bubble.hide()
    window._set_text('Segundo', 'happy', 'two')
    app.processEvents()
    assert window.bubble.pos() == manual_position
    assert window._bubble_manual_position == manual_position

    window.move(window.x() - 60, window.y() + 30)
    app.processEvents()
    screen = app.screenAt(window.frameGeometry().center()) or app.primaryScreen()
    expected = bubble_position(screen.availableGeometry(), window.frameGeometry(), window.bubble.size())
    assert window._bubble_manual_position is None
    assert window.bubble.pos() == expected
    window.close()

def test_vertical_lane_caps_manual_growth_before_the_avatar() -> None:
    """A manually placed bubble may grow only inside its detached lane."""
    screen = QRect(0, 0, 1200, 900)
    avatar = QRect(900, 620, 250, 260)
    bubble = QRect(650, 120, 480, 180)

    lane, maximum_height = bubble_vertical_lane(screen, avatar, bubble, True)

    assert lane == "above"
    assert maximum_height == bubble.bottom() - (screen.top() + 18)

def test_automatic_bubble_preserves_avatar_facing_edge_and_vertical_gap() -> None:
    """Automatic content resizing remains justified above the avatar without overlap."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    avatar = window.frameGeometry()
    window.bubble.resize(480, 180)
    window.bubble.move(avatar.right() - window.bubble.width(), avatar.top() - window.bubble.height() - 18)
    window.bubble.show()
    old_bottom = window.bubble.frameGeometry().bottom()

    long_message = "\n\n".join(f"L├¡nea {index} con contenido de validaci├│n." for index in range(24))
    window._set_bubble_message_anchored(long_message, "≡ƒÿè", "D:/workspace")
    app.processEvents()

    assert window._bubble_manual_position is None
    assert window.bubble.frameGeometry().bottom() == old_bottom
    assert window.bubble.frameGeometry().bottom() < avatar.top()
    window.close()

def test_bubble_resize_completion_notifies_manual_geometry() -> None:
    """Corner resizing must retain geometry just like a drag operation."""
    import inspect

    source = inspect.getsource(QtMarkdownBubble.mouseReleaseEvent)
    assert "self._resize_origin is not None" in source
    assert "self.manuallyMoved.emit()" in source

def test_detached_vertical_lane_uses_available_height_and_keeps_tail_on_avatar() -> None:
    """A long automatic message may fill its lane, never grow into the avatar."""
    app = QApplication.instance() or QApplication([])
    screen = QRect(0, 0, 1200, 1200)
    avatar = QRect(900, 800, 250, 320)
    bubble = QtMarkdownBubble()
    bubble.resize(480, 180)
    standard_maximum = bubble.maximumHeight()

    initial = bubble_position(screen, avatar, bubble.size())
    lane, available_height = bubble_vertical_lane(
        screen,
        avatar,
        QRect(initial, bubble.size()),
        preserve_position=False,
    )
    assert lane == "above"
    assert available_height is not None and available_height > standard_maximum

    bubble.set_vertical_height_limit(True, available_height)
    bubble.set_message("\n\n".join(f"P├írrafo detallado {index} con contenido suficiente para ocupar altura." for index in range(120)))
    app.processEvents()

    assert standard_maximum < bubble.height() <= available_height
    anchored = bubble_position(screen, avatar, bubble.size(), lane=lane)
    assert anchored.y() + bubble.height() - 5 == avatar.top()
    bubble.close()

def test_custom_chrome_scales_at_minimum_default_and_large_widths() -> None:
    app = QApplication.instance() or QApplication([])
    from brain.presentation.avatar.qt.controls import chrome_geometry
    window = QtAvatarWindow(start_polling=False)
    for width, height in ((150, 200), (260, 360), (500, 667)):
        window.resize(width, height)
        window.controls.resize(window.size())
        pin, message, grip = chrome_geometry(width, height)
        assert message.width() == round(pin.width() * 1.05)
        assert message.height() == message.width()
        assert message.top() == pin.top() - 3
        assert 32 <= pin.width() <= 46
        assert window.controls.rect().contains(pin.toAlignedRect())
        assert window.controls.rect().contains(message.toAlignedRect())
        assert window.controls.rect().contains(grip.toAlignedRect())
        assert not window.controls.grab().isNull()
    window.close()
    app.processEvents()

def test_pin_vector_changes_blue_and_white_with_pin_state() -> None:
    from brain.presentation.avatar.qt.controls import pin_fill_color
    assert pin_fill_color(True).name() == "#3b8cff"
    assert pin_fill_color(False).name() == "#f8fbff"

def test_avatar_grip_preserves_three_by_four_aspect_ratio() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.resize(240, 320)
    window.show()
    app.processEvents()
    start = QPoint(window.controls.width() - 8, window.controls.height() - 8)
    QTest.mousePress(window.controls, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(window.controls, start + QPoint(60, 15), delay=10)
    QTest.mouseRelease(window.controls, Qt.MouseButton.LeftButton, pos=start + QPoint(60, 15))
    assert abs(window.width() / window.height() - .75) < .01
    window.close()

def test_avatar_resize_grip_captures_pointer_until_outside_release() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.resize(240, 320)
    window.show()
    app.processEvents()
    start = QPoint(window.controls.width() - 8, window.controls.height() - 8)
    with patch.object(window.controls, "grabMouse") as grab, patch.object(window.controls, "releaseMouse") as release:
        QTest.mousePress(window.controls, Qt.MouseButton.LeftButton, pos=start)
        grab.assert_called_once_with()
        QTest.mouseMove(window.controls, QPoint(window.controls.width() + 90, window.controls.height() + 90), delay=10)
        QTest.mouseRelease(window.controls, Qt.MouseButton.LeftButton, pos=QPoint(window.controls.width() + 90, window.controls.height() + 90))
        release.assert_called_once_with()
    assert window.width() > 240
    assert abs(window.width() / window.height() - .75) < .01
    window.close()

def test_visible_bubble_tail_refreshes_after_native_avatar_move() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_text("Cola dinámica", "happy")
    app.processEvents()
    before_position = QPoint(window.bubble.pos())
    window.move(window.x() - 120, window.y() + 40)
    window._refresh_tail()
    assert window.bubble.pos() != before_position
    assert window.bubble._tail_target == window.bubble.mapFromGlobal(window.mapToGlobal(window.rect().center()))
    window.close()

def test_lower_left_resize_zone_does_not_steal_mute_click() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.resize(260, 360)
    window.show()
    app.processEvents()
    calls = []
    window.controls.on_mute = lambda: calls.append("mute")
    from brain.presentation.avatar.qt.controls import mute_geometry
    center, _radius = mute_geometry(window.controls.width(), window.controls.height())
    QTest.mouseClick(window.controls, Qt.MouseButton.LeftButton, pos=center.toPoint())
    assert calls == ["mute"]
    assert window.controls._resize_origin is None
    window.close()


def test_capture_geometry_stays_below_and_separate_from_pin_at_multiple_sizes() -> None:
    """Keep the screenshot control below the pin without intersecting it."""
    from brain.presentation.avatar.qt.controls.geometry import (
        capture_geometry,
        chrome_geometry,
    )

    for width, height in ((150, 200), (260, 360), (500, 667)):
        pin, _message, _grip = chrome_geometry(width, height)
        capture = capture_geometry(width, height)

        assert capture.top() > pin.bottom()
        assert not capture.intersects(pin)
