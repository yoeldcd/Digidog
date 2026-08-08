# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Qt avatar markdown, attachment, image, and table rendering tests."""
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
    original = "[Observo el visor.]\n\nUn [enlace](https://example.com) y ![una imagen](avatar.png)."
    source = avatar_markdown_source(original, "🩷")
    assert '> *🩷 Observo el visor.*' in source
    assert "[enlace](https://example.com)" in source
    assert "![una imagen](avatar.png)" in source

def test_avatar_markdown_preserves_inline_square_closures_and_emphasis() -> None:
    original = "Clausuras: **`[texto]` dentro de una oración**, (texto) y {texto}."
    source = avatar_markdown_source(original)
    assert source == original
    assert not source.startswith(">")

def test_avatar_markdown_materializes_explicit_newlines_and_inline_lists() -> None:
    source = normalize_avatar_markdown(r"Validacion:\n- Uno\n- Dos")
    assert source == "Validacion:\n- Uno\n- Dos"

def test_avatar_markdown_projects_long_comma_enumerations_as_lists() -> None:
    source = normalize_avatar_markdown("Incluye: uno, dos, tres, cuatro, cinco")
    assert source == "Incluye:\n\n- uno\n- dos\n- tres\n- cuatro\n- cinco"

def test_avatar_markdown_does_not_infer_lists_from_prose_or_multiline_blocks() -> None:
    prose = "Conserva esta frase - incluso con guiones - como un solo párrafo."
    commas = "uno, dos, tres, cuatro, cinco"
    multiline = "Resumen con uno, dos, tres, cuatro\ny una segunda línea"
    assert normalize_avatar_markdown(prose) == prose
    assert normalize_avatar_markdown(commas) == commas
    assert normalize_avatar_markdown(multiline) == multiline

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

def test_qt_bubble_keeps_unrequested_small_images_at_natural_size(tmp_path) -> None:
    """The shared bubble retains natural sizing without a host override."""
    app = QApplication.instance() or QApplication([])
    image_path = tmp_path / "small.png"
    image = QImage(24, 12, QImage.Format.Format_ARGB32)
    image.fill(QColor("pink"))
    assert image.save(str(image_path))
    bubble = QtMarkdownBubble()
    bubble.set_message(f"![Small]({image_path.as_uri()})")
    image_block = bubble.document_view.document().begin()
    image_format = image_block.begin().fragment().charFormat().toImageFormat()
    assert image_format.isValid()
    assert QSize(round(image_format.width()), round(image_format.height())) == image.size()
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

def test_qt_avatar_movie_renders_nontransparent_pixels_offscreen() -> None:
    """Prove the selected GIF reaches the QLabel as visible pixels without WinUI."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_state("awaiting", force=True)

    pixmap = QPixmap()
    for _ in range(25):
        app.processEvents()
        QTest.qWait(10)
        candidate = window.avatar.pixmap()
        if candidate is not None and not candidate.isNull():
            pixmap = candidate
            break

    assert not pixmap.isNull()
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    assert any(
        image.pixelColor(x, y).alpha() > 0
        for y in range(0, image.height(), max(1, image.height() // 40))
        for x in range(0, image.width(), max(1, image.width() // 40))
    )
    window.close()
    app.processEvents()

def test_qt_bubble_keeps_list_content_and_inline_typography_uniform_during_zoom() -> None:
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    bubble.set_message(
        "- Texto con `kind` y sufijo visible.\n"
        "- `get-context --json` permanece visible.\n"
        "- **Prueba fuerte** también visible.\n"
        "- Elemento ordinario visible."
    )
    html = bubble.document_view.document().toHtml()
    assert html.count("<li") == 4
    assert "sufijo visible" in html
    assert "permanece visible" in html
    assert "Prueba fuerte" in html

    def inline_fonts() -> list[tuple[str, str, float]]:
        fragments: list[tuple[str, str, float]] = []
        block = bubble.document_view.document().begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid() and fragment.text().strip():
                    font = fragment.charFormat().font()
                    fragments.append((fragment.text(), font.family(), font.pointSizeF()))
                iterator += 1
            block = block.next()
        return fragments

    before = inline_fonts()
    assert {family for _text, family, _size in before} == {"Arial"}
    QTest.mouseClick(bubble.zoom_in_button, Qt.MouseButton.LeftButton)
    after = inline_fonts()
    assert {family for _text, family, _size in after} == {"Arial"}
    assert len({size for _text, _family, size in after}) == 1
    assert after[0][2] > before[0][2]
    bubble.close()
    app.processEvents()

def test_conflicting_markdown_and_international_numbers_preserve_text() -> None:
    """Let Qt balance style conflicts without losing semantic characters."""
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    bubble.set_message('**Bold *Italic** Italic* | 1.234,56 | 1,234.56 | final')
    rendered = bubble.document_view.document().toPlainText()
    assert rendered == 'Bold Italic Italic | 1.234,56 | 1,234.56 | final'
    bubble.close()

def test_policy_codes_and_paths_preserve_characters_without_eating_r_or_n() -> None:
    """Ensure rec19, rec20, ./$agent/.tmp/ and numbered list formatting preserve r and n."""
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    text = (
        "1. Registré la Política **rec20** (Worker Execution Boundary Policy):\n"
        "   - Prohibición absoluta de crear scripts fuera de ./$agent/.tmp/\n"
        "   - Registro **rec19** completado."
    )
    bubble.set_message(text)
    plain_text = bubble.document_view.document().toPlainText()
    assert "rec20" in plain_text
    assert "rec19" in plain_text
    assert " ec20" not in plain_text
    assert " ec19" not in plain_text
    assert "$agent" in plain_text
    bubble.close()

def test_avatar_semantic_ranges_do_not_overlap_or_cross_paragraph_breaks() -> None:
    """Containers are transparent: children refine sub-ranges inside them."""
    text = "[presentation/actions avatar_layout_modal_composer.ts]\u2029next_line"
    ranges = semantic_token_ranges(text)

    tokens = [r[0] for r in ranges]
    assert "square" in tokens
    assert "snake" in tokens

    leaf_ranges = [(s, s + l) for tok, s, l, _w in ranges if tok not in {"square", "round", "curly"}]
    for i, (s1, e1) in enumerate(leaf_ranges):
        for s2, e2 in leaf_ranges[i + 1:]:
            assert e1 <= s2 or e2 <= s1, f"Leaf overlap: ({s1},{e1}) vs ({s2},{e2})"

def test_avatar_semantic_highlighting_preserves_every_rendered_character() -> None:
    """Applying token colors must never consume line endings or text suffixes."""
    app = QApplication.instance() or QApplication([])
    bubble = QtMarkdownBubble()
    bubble.set_message(
        "- presentation/actions\n"
        "- presentation/avatar/components avatar_layout_modal_composer.ts\n"
        "- models_speech_requests_contract y texto final"
    )
    rendered = bubble.document_view.document().toPlainText()

    assert "presentation/actions" in rendered
    assert "avatar_layout_modal_composer.ts" in rendered
    assert "models_speech_requests_contract y texto final" in rendered
    assert rendered.count("\n") == 2
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
    from brain.presentation.avatar.qt.markdown import AvatarTextBrowser
    assert AvatarTextBrowser.MAX_IMAGE_BYTES == 100 * 1024 * 1024

def test_content_columns_receive_most_avatar_table_width() -> None:
    assert table_column_percentages(['estado', 'dominio', 'tarea']) == [18.0, 18.0, 64.0]
    assert table_column_percentages(['source', 'content|entity']) == [36.0, 64.0]
    assert table_column_percentages(['unknown', 'value']) == [36.0, 64.0]

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
    widths = table.format().columnWidthConstraints()
    assert widths[0].rawValue() == 36.0
    assert widths[1].rawValue() == 64.0
    assert table.cellAt(1, 0).firstCursorPosition().blockFormat().alignment() == Qt.AlignmentFlag.AlignCenter
    assert table.cellAt(1, 1).firstCursorPosition().blockFormat().alignment() == Qt.AlignmentFlag.AlignLeft
    assert "border-bottom: 2px" in bubble.document_view.document().defaultStyleSheet()
    bubble.close()

def test_embedded_file_markers_render_as_a_bounded_markdown_attachment() -> None:
    source = (
        '<!-- avatar-file:start name="implementation-plan.md" -->\n\n'
        '## Step one\n\n- Validate behavior\n\n'
        '<!-- avatar-file:end -->'
    )
    rendered = render_embedded_file_blocks(source)
    assert '<!-- avatar-file:' not in rendered
    assert '> **📎 implementation-plan.md**' in rendered
    assert '> ## Step one' in rendered
    assert '> - Validate behavior' in rendered
    assert rendered.startswith('---')
    assert rendered.endswith('---')

    action_source = (
        '<!-- avatar-file:start name="implementation-plan.md" -->\n\n'
        '## 📎 implementation-plan.md\n\n# Step one\n\n'
        '<!-- avatar-file:end -->'
    )
    action_rendered = render_embedded_file_blocks(action_source)
    assert action_rendered.count('implementation-plan.md') == 1

def test_qt_embedded_file_message_persists_until_explicit_dismissal() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_text('Plan\n\n## File', 'focused', 'file-one', has_embedded_file=True)
    assert window.bubble.isVisible()
    window._set_text('', '')
    assert window.bubble.isVisible()
    assert not window.bubble_hide_timer.isActive()
    window._hide_bubble()
    assert window.bubble.isVisible()
    window._dismiss_bubble()
    assert not window.bubble.isVisible()
    window.close()
    app.processEvents()

def test_qt_normal_replacement_restores_speech_completion_auto_hide() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_text('Attached plan', 'focused', 'file-one', has_embedded_file=True)
    window._set_text('Ordinary message', 'happy', 'ordinary-two', has_embedded_file=False)
    assert window.current_has_embedded_file is False
    window._set_text('', '')
    assert window.bubble_hide_timer.isActive()
    window.close()
    app.processEvents()

def test_qt_history_carries_explicit_embedded_file_persistence() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    history = [
        {'id': 'latest', 'displayText': 'Latest', 'hasEmbeddedFile': False},
        {'id': 'file-one', 'displayText': 'Attached plan', 'hasEmbeddedFile': True, 'manualSpeech': True},
    ]
    with patch.object(window, '_message_history', return_value=history):
        window._navigate_message(-1)
    assert window.current_message_id == 'file-one'
    assert window.current_has_embedded_file is True
    assert window.current_manual_speech is True
    window._hide_bubble()
    assert window.bubble.isVisible()
    window._dismiss_bubble()
    assert not window.bubble.isVisible()
    window.close()


def test_avatar_markdown_formats_color_references() -> None:
    """Color references outside code blocks must be formatted with dot indicators."""
    from brain.presentation.avatar.interactivity.markdown_document import avatar_markdown_source

    source = "Color chips #ff9bd3, rgb(255, 100, 50), rgba(0, 128, 255, 0.5) y hsl(200, 80%, 60%)\n```\n#382a14\n```"
    result = avatar_markdown_source(source)
    assert "● #ff9bd3" in result
    assert "● rgb(255, 100, 50)" in result
    assert "● rgba(0, 128, 255, 0.5)" in result
    assert "● hsl(200, 80%, 60%)" in result
    assert "<pre><code>#382a14</code></pre>" in result


def test_avatar_semantic_angle_tags_and_isolated_math_symbols() -> None:
    """Angle tags take precedence while isolated < > ! are captured at math level."""
    from brain.presentation.avatar.qt.markdown.document import semantic_token_ranges

    text = "<div class=\"box\">tag</div> and x < 10 !="
    ranges = semantic_token_ranges(text)
    token_names = [r[0] for r in ranges]
    assert "angle" in token_names
    assert "math" in token_names
    assert "number" in token_names
