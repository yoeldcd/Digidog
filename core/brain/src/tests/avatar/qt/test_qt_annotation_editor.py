"""Focused TM-011 contracts for the native Qt annotation editor."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QColorDialog, QGroupBox

from brain.presentation.avatar.qt.backlog.annotation import (
    ANNOTATION_PALETTE,
    AnnotationCanvas,
    AnnotationDialog,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _canvas(width: int = 300, height: int = 200) -> AnnotationCanvas:
    _app()
    source = QPixmap(width, height)
    source.fill(QColor("white"))
    canvas = AnnotationCanvas(source)
    canvas.setMinimumSize(0, 0)
    canvas.resize(width, height)
    canvas.show()
    QApplication.processEvents()
    return canvas


def _drag(canvas: AnnotationCanvas, start: QPoint, end: QPoint, midpoint: QPoint | None = None) -> None:
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    if midpoint is not None:
        QTest.mouseMove(canvas, midpoint)
    QTest.mouseMove(canvas, end)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)


def test_dialog_applies_avatar_theme_to_controls_and_canvas() -> None:
    _app()
    source = QPixmap(80, 40)
    source.fill(QColor("white"))
    dialog = AnnotationDialog(source, theme="dark")
    assert dialog.theme_tokens.mode == "dark"
    assert dialog.canvas._background == QColor(dialog.theme_tokens.background)
    assert dialog.theme_tokens.surface in dialog.sidebar.styleSheet()


def test_dialog_groups_actions_and_projects_contextual_control_state() -> None:
    _app()
    dialog = AnnotationDialog(QPixmap(100, 60))
    assert dialog.width() == 720
    assert dialog.height() == 620
    assert not dialog.isModal()
    assert not hasattr(dialog, "color_selector")
    assert set(dialog.tool_buttons) == {"rectangle", "arrow", "path", "label"}
    assert dialog.tool_buttons["rectangle"].isChecked()
    groups = {group.title() for group in dialog.findChildren(QGroupBox)}
    assert groups == {"Tools", "Configuration/State"}
    assert not dialog.label_input.isHidden()
    assert not dialog.label_input.isEnabled()
    icon_buttons = [
        *dialog.tool_buttons.values(), dialog.color_button, dialog.copy_button,
        dialog.undo_button, dialog.redo_button, dialog.delete_button, dialog.clear_button,
    ]
    for button in icon_buttons:
        assert button.text() == button.accessibleName()
        assert not button.icon().isNull()
        assert button.accessibleName()
        assert button.toolTip()
    for button, label in ((dialog.save_button, "Save"), (dialog.close_button, "Cancel")):
        assert button.text() == label
        assert not button.icon().isNull()
        assert button.accessibleName() == label
        assert button.toolTip()
        assert button.parent() is dialog
        assert not dialog.sidebar.isAncestorOf(button)
    assert not dialog.undo_button.isEnabled()
    assert not dialog.redo_button.isEnabled()
    assert not dialog.delete_button.isEnabled()
    assert not dialog.clear_button.isEnabled()
    dialog.tool_buttons["label"].click()
    assert [tool for tool, button in dialog.tool_buttons.items() if button.isChecked()] == ["label"]
    assert dialog.label_input.isEnabled()
    dialog.tool_buttons["rectangle"].click()
    assert not dialog.label_input.isEnabled()
    dialog.canvas.setMinimumSize(0, 0)
    dialog.canvas.resize(100, 60)
    dialog.canvas.add_rectangle(QRect(10, 10, 40, 30))
    assert dialog.undo_button.isEnabled()
    assert dialog.clear_button.isEnabled()
    assert not dialog.delete_button.isEnabled()
    dialog.canvas.select_at(QPoint(10, 20))
    assert dialog.delete_button.isEnabled()
    dialog.delete_button.click()
    assert not dialog.delete_button.isEnabled()
    assert not dialog.clear_button.isEnabled()
    dialog.undo_button.click()
    assert dialog.redo_button.isEnabled()
    assert dialog.clear_button.isEnabled()
    dialog.close()


def test_dialog_resize_keeps_fixed_sidebar_and_expanding_canvas_separate() -> None:
    _app()
    dialog = AnnotationDialog(QPixmap(320, 180))
    dialog.setWindowState(Qt.WindowState.WindowNoState)
    dialog.show()

    canvas_widths: list[int] = []

    for size in ((1366, 768), (720, 620)):
        dialog.resize(*size)
        QApplication.processEvents()
        sidebar_geometry = dialog.sidebar.geometry()
        canvas_geometry = dialog.canvas.geometry()
        close_geometry = dialog.close_button.geometry()
        save_geometry = dialog.save_button.geometry()
        canvas_widths.append(canvas_geometry.width())
        assert dialog.sidebar.width() == 252
        assert sidebar_geometry.right() < canvas_geometry.left()
        assert not sidebar_geometry.intersects(canvas_geometry)
        assert canvas_geometry.bottom() < close_geometry.top()
        assert canvas_geometry.bottom() < save_geometry.top()
        assert sidebar_geometry.right() < close_geometry.left()
        assert close_geometry.right() < save_geometry.left()
        assert canvas_geometry.width() > 0
        assert canvas_geometry.height() > 0

    assert canvas_widths[0] > canvas_widths[1]
    dialog.close()


def test_rectangle_arrow_path_and_label_are_created_in_normalized_geometry() -> None:
    canvas = _canvas()
    _drag(canvas, QPoint(30, 30), QPoint(120, 100))
    canvas.set_tool("arrow")
    _drag(canvas, QPoint(140, 30), QPoint(240, 90))
    canvas.set_tool("path")
    _drag(canvas, QPoint(30, 140), QPoint(120, 170), QPoint(70, 155))
    canvas.set_tool("label")
    canvas.set_label("NOTE")
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(180, 150))

    assert [mark.kind for mark in canvas.marks] == ["rectangle", "arrow", "path", "label"]
    assert len(canvas.marks[2].points) >= 3
    assert canvas.marks[3].label == "NOTE"
    for mark in canvas.marks:
        left, top, right, bottom = canvas._bounds(mark)
        assert 0 <= left <= right <= 1
        assert 0 <= top <= bottom <= 1
    canvas.close()


def test_selection_move_recolor_relabel_delete_and_history() -> None:
    canvas = _canvas()
    canvas.add_rectangle(QRect(20, 20, 80, 60))
    assert canvas.select_at(QPoint(20, 40)) == 0
    canvas.move_selected(500, 500)
    moved = canvas.marks[0]
    assert moved.x + moved.width <= 1
    assert moved.y + moved.height <= 1
    canvas.apply_color("#123456")
    assert canvas.marks[0].color == "#123456"

    canvas.set_tool("label")
    canvas.set_label("OLD")
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(40, 160))
    canvas.set_label("NEW")
    assert canvas.marks[-1].label == "NEW"
    canvas.delete_selected()
    assert [mark.kind for mark in canvas.marks] == ["rectangle"]
    canvas.undo()
    assert [mark.kind for mark in canvas.marks] == ["rectangle", "label"]
    canvas.redo()
    assert [mark.kind for mark in canvas.marks] == ["rectangle"]
    canvas.clear_annotations()
    assert canvas.marks == ()
    canvas.undo()
    assert len(canvas.marks) == 1
    canvas.close()


def test_qcolor_dialog_applies_arbitrary_color(monkeypatch) -> None:
    _app()
    dialog = AnnotationDialog(QPixmap(100, 60))
    dialog.canvas.setMinimumSize(0, 0)
    dialog.canvas.resize(100, 60)
    dialog.canvas.add_rectangle(QRect(10, 10, 40, 30))
    dialog.canvas.select_at(QPoint(10, 20))
    monkeypatch.setattr(QColorDialog, "getColor", lambda *args, **kwargs: QColor("#654321"))
    dialog.choose_color()
    assert dialog.canvas.marks[0].color == "#654321"
    swatch = dialog.color_button.icon().pixmap(18, 18).toImage()
    assert any(
        swatch.pixelColor(x, y).name() == "#654321"
        for x in range(swatch.width())
        for y in range(swatch.height())
    )
    dialog.close()


def test_dpi_aware_preview_and_baked_png_share_normalized_pixel_position() -> None:
    _app()
    source = QPixmap(200, 100)
    source.setDevicePixelRatio(2.0)
    source.fill(QColor("white"))
    canvas = AnnotationCanvas(source)
    canvas.setMinimumSize(0, 0)
    canvas.resize(200, 200)
    canvas.show()
    QApplication.processEvents()
    assert canvas._image_rect() == QRect(0, 50, 200, 100)
    canvas.set_color("#ff0000")
    canvas.add_rectangle(QRect(20, 60, 40, 20))
    QApplication.processEvents()
    preview = canvas.grab().toImage()
    baked = canvas.baked_pixmap().toImage()
    assert baked.size().width() == 200
    assert baked.size().height() == 100
    assert preview.pixelColor(20, 60).red() > preview.pixelColor(20, 60).blue()
    assert baked.pixelColor(20, 10).red() > baked.pixelColor(20, 10).blue()
    canvas.close()


def test_copy_action_places_clean_result_pixmap_on_qt_clipboard() -> None:
    _app()
    source = QPixmap(100, 60)
    source.fill(QColor("white"))
    dialog = AnnotationDialog(source)
    dialog.canvas.setMinimumSize(0, 0)
    dialog.canvas.resize(100, 60)
    dialog.canvas.set_color("#ff0000")
    dialog.canvas.add_rectangle(QRect(10, 10, 40, 30))
    expected = dialog.result_pixmap().toImage()
    dialog.copy_button.click()
    copied = QApplication.clipboard().pixmap()
    assert not copied.isNull()
    assert copied.toImage() == expected
    dialog.close()

def test_export_is_source_sized_and_excludes_selection_chrome() -> None:
    canvas = _canvas(200, 100)
    canvas.set_color(ANNOTATION_PALETTE["Red"])
    canvas.add_rectangle(QRect(20, 20, 80, 50))
    canvas.select_at(QPoint(20, 40))
    with_selection = canvas.baked_pixmap().toImage()
    canvas.select_at(QPoint(-1, -1))
    without_selection = canvas.baked_pixmap().toImage()
    assert with_selection.size().width() == 200
    assert with_selection.size().height() == 100
    assert with_selection == without_selection
    assert with_selection != QPixmap(200, 100).toImage()
    canvas.close()


def test_marks_are_clipped_to_letterboxed_image_and_undo_redo_preserve_normalization() -> None:
    _app()
    source = QPixmap(200, 50)
    source.fill(QColor("white"))
    canvas = AnnotationCanvas(source)
    canvas.setMinimumSize(0, 0)
    canvas.resize(200, 200)
    canvas.add_rectangle(QRect(10, 60, 40, 50))
    assert canvas.rectangles == (QRect(10, 75, 40, 35),)
    original = canvas.marks
    canvas.clear_annotations()
    canvas.undo()
    assert canvas.marks == original
    canvas.redo()
    assert canvas.marks == ()
    canvas.close()