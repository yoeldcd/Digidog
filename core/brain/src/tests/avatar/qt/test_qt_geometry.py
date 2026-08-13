# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Qt avatar bubble, window, resize, and placement geometry tests."""
import json
import math
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
from brain.presentation.avatar.communication.contracts.models import CodexThreadTargetDTO
from brain.presentation.avatar.tk.avatar.window import AvatarWindow



def test_bubble_header_shows_emotion_repository_and_history_position() -> None:
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    bubble.resize(620, 180)
    bubble.set_message("Mensaje", "🩷", r"D:\repos\consumer", history_index=1, history_total=3)
    bubble.show()
    app.processEvents()
    assert "🩷" in bubble.source_label.text()
    assert bubble.source_label.toolTip() == r"D:\repos\consumer"
    assert bubble.history_label.text() == "2/3"
    assert bubble.backward_button.isEnabled()
    assert bubble.forward_button.isEnabled()
    assert bubble.zoom_out_button.accessibleName() == "Reducir mensaje"
    assert bubble.zoom_in_button.accessibleName() == "Ampliar mensaje"
    assert bubble.zoom_out_button.parentWidget() is bubble.footer
    assert bubble.zoom_in_button.parentWidget() is bubble.footer
    assert bubble.header.height() == 26
    assert bubble.footer.height() == 26
    assert bubble.layout().spacing() == 0
    assert bubble.source_label.font().pointSize() == 11
    assert bubble.close_button.geometry().center().y() == bubble.header.geometry().center().y()
    assert bubble.footer.y() + bubble.footer.height() <= bubble.height() - 24
    assert .98 <= bubble.separator_a_line.width() / bubble.separator_a.width() <= 1
    assert .98 <= bubble.separator_b_line.width() / bubble.separator_b.width() <= 1
    header_gap = bubble.document_view.y() - (bubble.header.y() + bubble.header.height())
    footer_gap = bubble.footer.y() - (bubble.document_view.y() + bubble.document_view.height())
    assert header_gap == footer_gap == 10
    bubble.close()


def test_footer_time_and_navigation_never_overlap_at_minimum_width() -> None:
    """Reserve independent footer regions so navigation keeps its hit boxes."""
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    bubble.resize(bubble.minimumWidth(), 180)
    bubble.show()
    app.processEvents()

    navigation = bubble.backward_button.geometry().united(bubble.forward_button.geometry())
    assert not bubble.remaining_label.geometry().intersects(navigation)
    assert bubble.backward_button.isVisible()
    assert bubble.backward_button.geometry().width() > 0
    bubble.close()

def test_bubble_remaining_counter_rounds_up_as_minutes_and_seconds() -> None:
    """Expose a stable mm:ss countdown without reporting negative time."""
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()

    bubble.set_remaining_seconds(65.01)
    assert bubble.remaining_label.text() == "01:06"
    assert bubble.remaining_label.accessibleName() == "Tiempo restante del mensaje"

    bubble.set_remaining_seconds(-1)
    assert bubble.remaining_label.text() == "00:00"
    bubble.close()

def test_bubble_tail_is_united_with_body_without_internal_seam() -> None:
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    bubble.resize(500, 180)
    bubble._tail_target = QPointF(bubble.width() / 2, bubble.height() + 50)
    bubble.show()
    app.processEvents()
    image = bubble.grab().toImage()
    seam = image.pixelColor(round(bubble.width() / 2), bubble.height() - 22)
    assert seam.name() == "#fff8fd"


def test_bubble_balances_outer_transparency_around_vertical_tail() -> None:
    """Balance the transparent viewport band around a vertical tail.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Opposite body edges share the same inset around the active tail.
    """
    QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    bubble.resize(500, 220)
    bubble._tail_target = QPointF(bubble.width() / 2, bubble.height() + 80)
    image = bubble.grab().toImage()

    middle_y = bubble.height() // 2
    for inset in (2, 4, 5, 6, 7, 10):
        left = image.pixelColor(inset, middle_y)
        right = image.pixelColor(bubble.width() - inset - 1, middle_y)
        assert left == right

    assert image.pixelColor(10, middle_y).alpha() > 0
    bubble.close()


def test_bubble_handle_hit_targets_match_fully_visible_painted_centers() -> None:
    """Use the same inset centers for corner detection and handle painting.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: Every hovered handle is fully visible and detected at its center.
    """
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    bubble.resize(500, 220)
    bubble.show()
    for corner in ("nw", "ne", "sw", "se"):
        body = bubble._bubble_body_rect()
        centers = {
            "nw": body.topLeft(),
            "ne": body.topRight(),
            "sw": body.bottomLeft(),
            "se": body.bottomRight(),
        }
        center = centers[corner]
        assert bubble._resize_corner(center) == corner
        bubble._hover_corner = corner
        bubble.update()
        app.processEvents()
        image = bubble.grab().toImage()
        point = center.toPoint()
        colors = {
            image.pixelColor(point + QPoint(dx, dy)).name()
            for dx in range(-3, 4)
            for dy in range(-3, 4)
        }
        assert "#f062b7" in colors

    bubble.close()

def test_short_message_height_keeps_complete_document_above_footer() -> None:
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    bubble.resize(620, 180)
    bubble.set_message("## Encabezado\n\nTexto final que nunca debe quedar ocluido.")
    bubble.show()
    app.processEvents()
    document_height = bubble.document_view.document().documentLayout().documentSize().height()
    assert bubble.height() < bubble.maximumHeight()
    assert bubble.document_view.viewport().height() >= document_height
    assert bubble.document_view.verticalScrollBar().maximum() == 0
    bubble.close()


def test_close_dismisses_current_synthesis_until_text_changes() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_text("Mensaje hablado", "happy")
    window.bubble._dismiss()
    window._set_text("Mensaje hablado", "happy")
    assert not window.bubble.isVisible()
    window._set_text("Mensaje nuevo", "happy")
    assert window.bubble.isVisible()
    window.close()
    app.processEvents()


def test_bubble_placement_and_indefinite_quota_fallback() -> None:
    screen = QRect(0, 0, 1200, 800)
    avatar = QRect(900, 300, 250, 400)
    point = bubble_position(screen, avatar, QSize(500, 180))
    assert screen.adjusted(18, 18, -18, -18).contains(QRect(point, QSize(500, 180)))
    assert point.y() < avatar.top()
    assert point.x() == avatar.right() - 500
    top_avatar = QRect(50, 20, 250, 300)
    near_top = bubble_position(screen, top_avatar, QSize(500, 180))
    assert near_top.y() == top_avatar.bottom() - 5
    no_vertical_room = bubble_position(QRect(0, 0, 1200, 400), QRect(900, 100, 250, 200), QSize(500, 260))
    assert no_vertical_room.x() < 900
    assert quota_reset_label(0, False) == "--:--"

def test_reply_composer_matches_bubble_width_and_viewport_direction() -> None:
    screen = QRect(0, 0, 1200, 800)
    bubble = QRect(500, 180, 620, 260)
    above = reply_composer_geometry(screen, bubble, True)
    assert above.width() == bubble.width()
    assert above.x() == bubble.x()
    assert above.top() == screen.top() + 18
    assert above.bottom() == bubble.bottom()
    below = reply_composer_geometry(screen, bubble, False)
    assert below.width() == bubble.width()
    assert below.top() == bubble.top()
    assert below.bottom() == screen.bottom() - 18


def test_reply_composer_geometry_can_preserve_bubble_horizontal_anchor() -> None:
    """Allow a screen-edge bubble frame to retain its exact horizontal rectangle."""
    screen = QRect(0, 0, 800, 800)
    bubble = QRect(40, 467, 760, 260)

    geometry = reply_composer_geometry(
        screen,
        bubble,
        True,
        horizontal_margin=0,
    )

    assert geometry.left() == bubble.left()
    assert geometry.width() == bubble.width()
    assert screen.contains(geometry)

def test_reply_composer_geometry_clamps_to_screen_and_safe_minimum() -> None:
    screen = QRect(0, 0, 500, 260)
    bubble = QRect(380, 20, 240, 180)
    minimum = QSize(420, 220)

    geometry = reply_composer_geometry(
        screen, bubble, True, minimum_size=minimum
    )
    safe_area = screen.adjusted(18, 18, -18, -18)

    assert safe_area.contains(geometry)
    assert geometry.width() >= min(minimum.width(), safe_area.width())
    assert geometry.height() >= min(minimum.height(), safe_area.height())


def test_bubble_manual_position_width_and_bottom_survive_content_and_hide_show() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_text("Primer mensaje", "happy", "one")
    app.processEvents()

    window.bubble.move(QPoint(40, 80))
    window._retain_bubble_offset()
    window.bubble.resize(480, 240)
    window.bubble._manual_size = True
    app.processEvents()
    retained_x = window.bubble.x()
    retained_width = window.bubble.width()
    retained_bottom = window.bubble.frameGeometry().bottom()

    window._set_text("Segundo mensaje con más contenido", "happy", "two")
    app.processEvents()
    assert window.bubble.x() == retained_x
    assert window.bubble.width() == retained_width
    assert window.bubble.frameGeometry().bottom() == retained_bottom

    window._dismiss_bubble()
    window._toggle_last_message()
    app.processEvents()
    assert window.bubble.isVisible()
    assert window.bubble.x() == retained_x
    assert window.bubble.width() == retained_width
    assert window.bubble.frameGeometry().bottom() == retained_bottom

    window.close()
    app.processEvents()


def test_avatar_move_resets_visible_and_hidden_auxiliary_geometry() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)

    with (
        patch.object(window.reply_window._controller, "open"),
        patch.object(window.reply_window._controller, "close"),
    ):
        window.show()
        window._set_text("Mensaje retenido", "happy", "one")
        app.processEvents()

        window.bubble.move(QPoint(40, 80))
        window._retain_bubble_offset()
        window.bubble.resize(480, 240)
        window.bubble._manual_size = True

        window.reply_window.show()
        window.reply_window.setGeometry(QRect(100, 100, 420, 240))
        app.processEvents()
        assert window.reply_window._manual_geometry is not None
        assert window.reply_window.isVisible()

        window.move(window.pos() + QPoint(12, 12))
        app.processEvents()

        assert window._bubble_manual_position is None
        assert window.bubble._manual_size is False
        assert window.reply_window._manual_geometry is None
        assert window.reply_window.isVisible()

        window.reply_window.hide()
        screen = window.app.screenAt(window.frameGeometry().center()) or window.app.primaryScreen()
        assert screen is not None
        automatic = reply_composer_geometry(
            screen.availableGeometry(),
            window.bubble.frameGeometry(),
            window._bubble_is_above_avatar(),
            minimum_size=window.reply_window.safe_minimum_size(),
        )
        target = CodexThreadTargetDTO(instance_id="reply-after-avatar-move")
        window.reply_window.open_for(target, automatic)
        app.processEvents()
        assert window.reply_window.isVisible()
        assert window.reply_window.geometry() == window.reply_window._bounded_geometry(automatic)

        window.close()
        app.processEvents()

def test_message_height_is_temporary_but_width_is_stable() -> None:
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    bubble.resize(540, 200)
    bubble.show()
    app.processEvents()
    bubble.set_message("Mensaje breve")
    app.processEvents()
    short_height = bubble.height()
    bubble.set_message("\n\n".join(f"Línea larga {index}" for index in range(100)))
    assert bubble.width() == 540
    assert bubble.height() == bubble.maximumHeight()
    bubble.set_message("Breve otra vez")
    app.processEvents()
    assert bubble.width() == 540
    assert bubble.height() == short_height
    bubble.close()


def test_message_height_matches_rendered_body_when_content_grows_and_shrinks() -> None:
    """Fit total bubble height to rendered body content in both directions."""
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    bubble.resize(540, 200)
    bubble.show()

    def expected_height() -> int:
        """Return the production body-height formula for current content."""
        app.processEvents()
        document = bubble.document_view.document()
        document.setTextWidth(max(220, bubble.document_view.width()))
        content = math.ceil(document.documentLayout().documentSize().height())
        margins = bubble.layout().contentsMargins()
        chrome = margins.top() + margins.bottom()
        chrome += sum(
            widget.height()
            for widget in (
                bubble.header,
                bubble.footer,
                bubble.separator_a,
                bubble.separator_b,
            )
        )
        chrome += bubble.layout().spacing() * (bubble.layout().count() - 1)
        requested = content + chrome + 16

        return max(bubble.minimumHeight(), min(bubble.maximumHeight(), requested))

    bubble.set_message("Mensaje breve")
    app.processEvents()
    short_height = bubble.height()
    assert short_height == expected_height()

    bubble.set_message("\n\n".join(f"Párrafo largo {index}" for index in range(40)))
    app.processEvents()
    long_height = bubble.height()
    assert long_height == expected_height()
    assert long_height > short_height

    bubble.set_message("Breve de nuevo")
    app.processEvents()
    assert bubble.height() == expected_height()
    assert bubble.height() < long_height
    bubble.close()


def test_manual_resize_preserves_width_but_content_still_shrinks_height() -> None:
    """Keep manual width while allowing every message body to refit height."""
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    bubble.resize(500, 360)
    bubble._manual_size = True
    bubble.show()

    bubble.set_message("\n\n".join(f"Contenido largo {index}" for index in range(50)))
    app.processEvents()
    long_height = bubble.height()

    bubble.set_message("Mensaje corto")
    app.processEvents()

    assert bubble.width() == 500
    assert bubble.height() < long_height
    assert bubble.document_view.verticalScrollBar().maximum() == 0
    bubble.close()

def test_repeated_status_does_not_reflow_or_move_dialogue() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_text("Texto estable que no debe saltar", "happy")
    app.processEvents()
    geometry = window.bubble.geometry()
    document_size = window.bubble.document_view.document().size()
    window._set_text("Texto estable que no debe saltar", "happy")
    app.processEvents()
    assert window.bubble.geometry() == geometry
    assert window.bubble.document_view.document().size() == document_size
    window.close()



def test_identical_new_message_id_overrides_previous_dismissal() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_text("Mensaje idéntico", "happy", "speak-one")
    window.bubble._dismiss()
    window._set_text("Mensaje idéntico", "happy", "speak-one")
    assert not window.bubble.isVisible()
    window.active_speak_id = "speak-two"
    window.active_presentation_owned = True
    window._set_state("speaking", emotion="happy")
    window._set_text("Mensaje idéntico", "happy", "speak-two")
    assert window.bubble.isVisible()
    assert window.controls.playing is True
    window.close()




def test_visible_manual_bubble_x_width_and_bottom_survive_new_content() -> None:
    """Incoming content may change only height around the retained bottom edge."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_text("Primer mensaje", "happy", "one")
    app.processEvents()
    manual_position = QPoint(48, 52)
    window.bubble.move(manual_position)
    window._retain_bubble_offset()
    manual_width = window.bubble.width()
    manual_bottom = window.bubble.frameGeometry().bottom()

    window._set_text("Segundo mensaje con una altura de contenido distinta.\n\nOtra l├¡nea.", "happy", "two")
    app.processEvents()

    assert window.bubble.x() == manual_position.x()
    assert window.bubble.width() == manual_width
    assert window.bubble.frameGeometry().bottom() == manual_bottom
    assert window._bubble_manual_position is not None
    assert window._bubble_manual_position.x() == manual_position.x()
    assert window._bubble_manual_bottom == manual_bottom
    window.close()


def test_manual_bubble_uses_viewport_edge_without_automatic_tail_margin() -> None:
    """Clamp manual placement only at the physical viewport edge.

    Args:
        No external arguments are accepted; pytest invokes the scenario.

    Returns:
        None: The retained X reaches the viewport edge and survives new content.
    """
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_text("Primer mensaje", "happy", "edge-one")
    app.processEvents()
    screen = window.app.screenAt(window.frameGeometry().center()) or window.app.primaryScreen()
    assert screen is not None
    viewport = screen.availableGeometry()
    edge_position = QPoint(viewport.left(), window.bubble.y())
    window.bubble.move(edge_position)
    window._retain_bubble_offset()

    window._set_text("Segundo mensaje", "happy", "edge-two")
    app.processEvents()

    assert window.bubble.x() == viewport.left()
    assert window._bubble_manual_position is not None
    assert window._bubble_manual_position.x() == viewport.left()
    window.close()



def test_bubble_preserves_safe_minimum_and_only_removes_vertical_maximum() -> None:
    """Protect chrome at minimum height and uncap only vertical placement."""
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    standard = bubble.maximumHeight()
    assert bubble.minimumHeight() >= 156
    bubble.set_vertical_height_limit(True)
    assert bubble.maximumHeight() == 16_777_215
    assert bubble.minimumHeight() >= 156
    bubble.set_vertical_height_limit(True, 360)
    assert bubble.maximumHeight() == 360
    bubble.set_vertical_height_limit(False)
    assert bubble.maximumHeight() == standard
    bubble.close()


def test_corner_resize_refreshes_vertical_limit_from_live_anchor_edge() -> None:
    """Allow repeated manual height growth to the full viewport lane."""
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    screen = app.primaryScreen()
    assert screen is not None
    viewport = screen.availableGeometry()
    bubble.resize(500, 220)
    bubble.move(viewport.left() + 40, viewport.bottom() - 260)
    bubble._tail_target = QPointF(bubble.width() / 2, bubble.height() + 80)
    bubble.setMaximumHeight(240)

    bubble._refresh_resize_height_limit()

    expected = bubble.frameGeometry().bottom() - viewport.top() + 1
    assert bubble.maximumHeight() == expected
    assert bubble.maximumHeight() > 240
    bubble.close()








def test_qt_dialogue_debounces_transient_empty_status() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_text("**Primer mensaje**", "happy")
    assert window.bubble.isVisible()
    window._set_text("", "")
    assert window.bubble_hide_timer.isActive()
    assert window.bubble.isVisible()
    window._set_text("**Segundo mensaje**", "happy")
    assert not window.bubble_hide_timer.isActive()
    assert window.bubble.isVisible()
    window.close()
    app.processEvents()
