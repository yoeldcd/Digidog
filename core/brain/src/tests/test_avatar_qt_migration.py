# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Safe first-slice tests for the optional Qt avatar presentation."""
import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtTest import QTest

from brain.presentation.avatar.window.backend import requested_avatar_backend, resolve_avatar_window_class
from brain.presentation.avatar.interactivity.markdown_document import (
    avatar_markdown_source,
    expand_avatar_images,
    normalize_avatar_markdown,
)
from brain.presentation.avatar.qt.markdown_bubble import QtMarkdownBubble, normalized_image_size
from brain.presentation.avatar.qt.window import (
    QtAvatarWindow,
    bubble_position,
    fit_avatar_frame,
    quota_reset_label,
    reply_composer_geometry,
)
from brain.presentation.avatar.tk.window import AvatarWindow


def test_backend_defaults_to_qt_and_keeps_explicit_tk_fallback() -> None:
    assert requested_avatar_backend({}) == "qt"
    assert resolve_avatar_window_class({}) is QtAvatarWindow
    assert resolve_avatar_window_class({"BRAIN_AVATAR_UI": "tk"}) is AvatarWindow
    assert requested_avatar_backend({"BRAIN_AVATAR_UI": "QT"}) == "qt"
    assert requested_avatar_backend({"BRAIN_AVATAR_UI": "unknown"}) == "qt"
    assert resolve_avatar_window_class({"BRAIN_AVATAR_UI": "qt"}) is QtAvatarWindow


def test_qt_avatar_body_click_preserves_playback_and_reactions() -> None:
    """Qt delays Play briefly so a double click remains a reaction gesture."""
    import inspect

    source = inspect.getsource(QtAvatarWindow._avatar_click)
    reaction_source = inspect.getsource(QtAvatarWindow._speak_reaction)
    assert "avatar_click_timer.isActive()" in source
    assert "_speak_reaction()" in source
    assert '"emotion": "reacting"' in reaction_source


def test_avatar_markdown_preserves_narrative_and_dialogue_semantics() -> None:
    source = avatar_markdown_source(
        "[Meneo la colita con cuidado.] **Hola**, papi.\n\n- Uno\n- Dos",
        "🩷",
    )
    assert source.startswith("> *🩷 Meneo la colita con cuidado.*")
    assert "**Hola**" in source
    assert "- Uno" in source


def test_avatar_markdown_adds_visual_section_rules_after_subheadings() -> None:
    source = avatar_markdown_source("# Principal\n\n## Sección\n\nContenido")
    assert "# Principal\n\n## Sección\n\n---\n\nContenido" in source


def test_avatar_markdown_does_not_confuse_links_or_images_with_narrative() -> None:
    original = "[Observo el visor.] Un [enlace](https://example.com) y ![una imagen](avatar.png)."
    source = avatar_markdown_source(original, "🩷")
    assert "> *🩷 Observo el visor.*" in source
    assert "[enlace](https://example.com)" in source
    assert "![una imagen](avatar.png)" in source


def test_avatar_markdown_materializes_explicit_newlines_and_inline_lists() -> None:
    source = normalize_avatar_markdown(r"Validacion:\n- Uno\n- Dos")
    assert source == "Validacion:\n- Uno\n- Dos"


def test_avatar_markdown_projects_long_comma_enumerations_as_lists() -> None:
    source = normalize_avatar_markdown("Incluye: uno, dos, tres, cuatro, cinco")
    assert source == "Incluye:\n\n- uno\n- dos\n- tres\n- cuatro\n- cinco"


def test_avatar_markdown_preserves_code_escapes_and_short_prose() -> None:
    source = normalize_avatar_markdown(r"`valor\ncrudo` y uno, dos, tres")
    assert r"`valor\ncrudo`" in source
    assert "- uno" not in source


def test_extended_markdown_images_emit_bounded_html_dimensions() -> None:
    source = expand_avatar_images("![Vista](https://example.com/image.png){width=320 height=9999}")
    assert source == '<img src="https://example.com/image.png" alt="Vista" width="320" height="1200">'


def test_qt_bubble_normalizes_html_image_dimensions_without_distortion() -> None:
    import tempfile
    from pathlib import Path
    from PySide6.QtGui import QImage

    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as directory:
        image_path = Path(directory) / "sample.png"
        image = QImage(4, 4, QImage.Format.Format_ARGB32)
        image.fill(QColor("pink"))
        assert image.save(str(image_path))
        bubble = QtMarkdownBubble()
        bubble.set_message(f'<img src="{image_path.as_posix()}" width="240" height="120">')
        html = bubble.document_view.document().toHtml()
        assert 'width="120"' in html
        assert 'height="120"' in html
        image_block = bubble.document_view.document().begin()
        assert image_block.blockFormat().alignment() == Qt.AlignmentFlag.AlignCenter
        bubble.close()
    app.processEvents()


def test_normalized_image_size_fits_requested_box_and_viewport() -> None:
    """Preserve intrinsic ratio while respecting both author and viewport bounds."""
    square = normalized_image_size(QSize(400, 400), (240, 120), QSize(600, 300))
    landscape = normalized_image_size(QSize(1600, 900), (None, None), QSize(500, 220))

    assert square == QSize(120, 120)
    assert landscape == QSize(391, 220)


def test_qt_bubble_renders_markdown_offscreen() -> None:
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    bubble.set_message("[Pienso.] **Markdown** y `código`.", "🩷")
    html = bubble.document_view.document().toHtml()
    assert "Pienso." in html
    assert "font-weight:700" in html or "font-weight:600" in html
    assert "código" in html
    assert "Arial" in html
    assert "#211522" in bubble.document_view.document().defaultStyleSheet()
    assert bubble.close_button.accessibleName() == "Cerrar mensaje"
    assert bubble.backward_button.accessibleName() == "Mensaje anterior"
    assert bubble.forward_button.accessibleName() == "Mensaje siguiente"
    assert bubble.backward_button.parentWidget() is bubble.footer
    assert bubble.forward_button.parentWidget() is bubble.footer
    assert bubble.source_label.parentWidget() is bubble.header
    assert 220 <= bubble.maximumHeight() <= 420
    bubble.set_message("\n\n".join(f"## Sección {index}\nContenido largo" for index in range(80)))
    bubble.show()
    app.processEvents()
    assert bubble.height() == bubble.maximumHeight()
    assert bubble.document_view.verticalScrollBar().maximum() > 0
    bubble.close()
    app.processEvents()


def test_qt_bubble_applies_contrast_safe_dark_and_light_links() -> None:
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    bubble.set_theme("dark")
    dark_css = bubble.document_view.document().defaultStyleSheet()
    assert "#ff9bd3" in dark_css
    assert bubble.property("avatarTheme") == "dark"
    assert "background: #302832" in bubble.backward_button.styleSheet()
    assert "color: #ffb6df" in bubble.zoom_in_button.styleSheet()
    bubble.set_theme("light")
    light_css = bubble.document_view.document().defaultStyleSheet()
    assert "#78124e" in light_css
    assert bubble.property("avatarTheme") == "light"
    assert "background: #fff1f8" in bubble.backward_button.styleSheet()
    assert "color: #6f3158" in bubble.zoom_in_button.styleSheet()
    bubble.close()
    app.processEvents()


def test_avatar_image_viewer_allows_large_external_resources() -> None:
    from brain.presentation.avatar.qt.markdown_bubble import AvatarTextBrowser
    assert AvatarTextBrowser.MAX_IMAGE_BYTES == 100 * 1024 * 1024


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


def test_bubble_zoom_controls_and_footer_actions_follow_avatar_alignment() -> None:
    """Keep zoom bounded and group actions on the avatar-facing footer side."""
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    bubble.set_message("Mensaje de prueba")
    bubble.show()
    app.processEvents()

    QTest.mouseClick(bubble.zoom_in_button, Qt.MouseButton.LeftButton)
    assert bubble._zoom_step == 1
    assert bubble.footer_layout.indexOf(bubble.reply_button) < bubble.footer_layout.indexOf(bubble.backward_button)
    navigation_center = (bubble.backward_button.x() + bubble.forward_button.geometry().right()) / 2
    assert abs(navigation_center - bubble.footer.width() / 2) <= 4

    bubble.set_tail_target(bubble.mapToGlobal(QPoint(bubble.width(), bubble.height() // 2)))
    assert bubble.footer_layout.indexOf(bubble.reply_button) > bubble.footer_layout.indexOf(bubble.forward_button)
    app.processEvents()
    navigation_center = (bubble.backward_button.x() + bubble.forward_button.geometry().right()) / 2
    assert abs(navigation_center - bubble.footer.width() / 2) <= 4

    for _ in range(8):
        QTest.mouseClick(bubble.zoom_out_button, Qt.MouseButton.LeftButton)
    assert bubble._zoom_step == -3
    assert not bubble.zoom_out_button.isEnabled()
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


def test_bubble_placement_and_indefinite_quota_fallback() -> None:
    screen = QRect(0, 0, 1200, 800)
    avatar = QRect(900, 300, 250, 400)
    point = bubble_position(screen, avatar, QSize(500, 180))
    assert screen.adjusted(18, 18, -18, -18).contains(QRect(point, QSize(500, 180)))
    assert point.y() < avatar.top()
    assert point.x() == avatar.right() - 500
    near_top = bubble_position(screen, QRect(50, 20, 250, 300), QSize(500, 180))
    assert near_top.y() > 20 + 300
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


def test_avatar_drag_and_both_resize_affordances_are_reachable() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
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
    assert bubble._resize_corner(QPointF(22, 22)) == "nw"
    window.close()


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
    assert controls.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
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

def test_processing_states_use_animated_dots_without_transient_bubbles() -> None:
    """Thinking and preparation belong to top chrome rather than message history."""
    import inspect

    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window._set_state("thinking")
    assert window.controls.processing is True
    assert window.controls.processing_timer.isActive()
    window._set_state("awaiting")
    assert window.controls.processing is False
    assert not window.controls.processing_timer.isActive()
    poll_source = inspect.getsource(QtAvatarWindow._poll)
    assert 'processing_emotion = str(payload.get("processingEmotion", ""))' in poll_source
    assert 'processing=processing or state in {"thinking", "preparing"}' in poll_source
    assert 'if state in {"thinking", "preparing"}' in poll_source
    assert poll_source.index('if state in {"thinking", "preparing"}') < poll_source.index("self._set_text(")
    window.close()


def test_processing_indicator_reuses_explorer_working_palette() -> None:
    """Qt presents the same six semantic dot colors used by Brain Explorer."""
    import inspect

    from brain.presentation.avatar.qt.controls import QtAvatarControls

    source = inspect.getsource(QtAvatarControls._paint_processing)
    for color in ("#3b82f6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#ec4899"):
        assert color in source
    assert "pin_bounds.right() + message_bounds.left()" in source

def test_message_icon_fills_white_and_centers_red_buffer_count() -> None:
    """The queue depth is text inside the bubble, never a detached badge circle."""
    import inspect

    from brain.presentation.avatar.qt.controls import QtAvatarControls

    source = inspect.getsource(QtAvatarControls._paint_show_message)
    assert 'painter.setBrush(QColor("#ffffff"))' in source
    assert 'painter.setPen(QColor("#e32636"))' in source
    assert "painter.drawText(bubble_bounds, Qt.AlignmentFlag.AlignCenter, buffer_text)" in source
    assert 'buffer_text = "99+" if self.queue_depth > 99' in source
    assert "drawEllipse" not in source

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

def test_message_control_toggles_visual_without_replay() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_text("Mensaje retenido", "happy", "speak-one")
    assert window.bubble.isVisible()
    with patch.object(window, "_post") as post:
        window._toggle_last_message()
        assert not window.bubble.isVisible()
        window._toggle_last_message()
    assert window.bubble.isVisible()
    post.assert_not_called()
    window.close()


def test_history_playback_targets_the_audio_fixed_in_the_bubble() -> None:
    """Play requeues the selected retained audio instead of the newest message."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.message_reveal_latched = True
    window.current_audio_name = "retained-message.mp3"
    window.current_display_text = "Mensaje histórico"
    with patch.object(window, "_post") as post:
        window._toggle_playback()
    post.assert_called_once_with("/replay", {"name": "retained-message.mp3"})
    window.close()


def test_history_without_retained_audio_queues_its_fixed_text() -> None:
    """A fixed message remains playable when its original audio was not retained."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.message_reveal_latched = True
    window.current_audio_name = ""
    window.current_display_text = "Mensaje histórico"
    window.current_codex_thread_id = "thread-one"
    with patch.object(window, "_post") as post:
        window._toggle_playback()
    endpoint, payload = post.call_args.args
    assert endpoint == "/speak"
    assert payload["text"] == "Mensaje histórico"
    assert payload["sourcePhase"] == "replay"
    assert payload["codexThreadId"] == "thread-one"
    window.close()


def test_message_history_links_each_speak_to_its_retained_audio() -> None:
    """History records expose the audio name selected by their speak identifier."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    with patch("brain.presentation.avatar.qt.window.urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = (
            b'{"speaks":[{"id":"speak-one","text":"Uno"}],'
            b'"messages":[{"speakId":"speak-one","name":"one.mp3"}]}'
        )
        history = window._message_history()
    assert history[0]["audioName"] == "one.mp3"
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
        assert window.bubble.history_label.text() == "2/2"
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


def test_message_below_avatar_grows_downward_from_fixed_top() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
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


def test_identical_new_message_id_overrides_previous_dismissal() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_text("Mensaje idéntico", "happy", "speak-one")
    window.bubble._dismiss()
    window._set_text("Mensaje idéntico", "happy", "speak-one")
    assert not window.bubble.isVisible()
    window._set_state("speaking", emotion="happy")
    window._set_text("Mensaje idéntico", "happy", "speak-two")
    assert window.bubble.isVisible()
    assert window.controls.playing is True
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


def test_markdown_tables_use_strong_rules_and_semantic_alignment() -> None:
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    bubble.set_message(
        "## Sección\n\n| Corto | Descripción |\n|---|---|\n"
        "| Sí | Esta celda contiene un texto suficientemente largo |",
    )
    tables = [frame for frame in bubble.document_view.document().rootFrame().childFrames() if hasattr(frame, "cellAt")]
    assert len(tables) == 1
    table = tables[0]
    assert table.format().border() >= 2
    assert table.cellAt(1, 0).firstCursorPosition().blockFormat().alignment() == Qt.AlignmentFlag.AlignCenter
    assert table.cellAt(1, 1).firstCursorPosition().blockFormat().alignment() == Qt.AlignmentFlag.AlignLeft
    assert "border-bottom: 2px" in bubble.document_view.document().defaultStyleSheet()
    bubble.close()


def test_custom_chrome_scales_at_minimum_default_and_large_widths() -> None:
    app = QApplication.instance() or QApplication([])
    from brain.presentation.avatar.qt.controls import chrome_geometry
    window = QtAvatarWindow(start_polling=False)
    for width, height in ((150, 200), (260, 360), (500, 667)):
        window.resize(width, height)
        window.controls.resize(window.size())
        pin, message, grip = chrome_geometry(width, height)
        assert pin.size() == message.size()
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


def test_qt_pin_priority_is_synchronized_with_bubble() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window._set_text("Mensaje visible", "happy")
    window._toggle_pin(False)
    assert not bool(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
    assert not bool(window.bubble.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
    window._toggle_pin(True)
    assert bool(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
    assert bool(window.bubble.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
    window.close()
    app.processEvents()


def test_processing_orbit_is_stable_and_centers_speak_emotion() -> None:
    """Processing uses a fixed-radius orbit and a canonical center emoji."""
    import inspect

    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    controls = window.controls
    controls.set_processing(True, "focused")

    assert controls.processing_emotion == "focused"
    source = inspect.getsource(controls._paint_processing)
    assert "orbit_radius" in source
    assert "pulse" not in source
    assert "self._paint_processing_emotion(painter, center)" in source
    controls.set_processing(True, "happy")
    assert controls.processing_frame == 0
    assert controls.processing_emotion == "happy"
    controls.set_processing(False)
    assert controls.processing_emotion == ""
    window.close()