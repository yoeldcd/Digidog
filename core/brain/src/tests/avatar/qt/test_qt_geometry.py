# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Qt avatar bubble, window, resize, and placement geometry tests."""
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




def test_visible_manual_bubble_origin_survives_new_message_content() -> None:
    """Incoming content must not replace a retained user origin with an automatic anchor."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_text("Primer mensaje", "happy", "one")
    app.processEvents()
    manual_position = QPoint(48, 52)
    window.bubble.move(manual_position)
    window._retain_bubble_offset()

    window._set_text("Segundo mensaje con una altura de contenido distinta.\n\nOtra l├¡nea.", "happy", "two")
    app.processEvents()

    assert window.bubble.pos() == manual_position
    assert window._bubble_manual_position == manual_position
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
