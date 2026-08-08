"""Normalized canvas interaction and rendering for Qt backlog annotations."""
from __future__ import annotations

from dataclasses import replace
import math

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QWidget

from brain.presentation.avatar.qt.backlog.annotation.models import (
    ANNOTATION_PALETTE,
    ANNOTATION_TOOLS,
    AnnotationGesture,
    AnnotationMark,
)


class AnnotationCanvas(QWidget):
    """Own normalized marks, editor history, selection, and image-safe gestures."""

    stateChanged = Signal()

    def __init__(self, pixmap: QPixmap, parent: QWidget | None = None) -> None:
        """Initialize the normalized annotation canvas and its history state.
        
        Args:
            pixmap: Pixmap rendered inside the canvas.
            parent: Optional Qt owner for lifecycle management."""
        super().__init__(parent)
        self._pixmap = QPixmap(pixmap)
        self._marks: list[AnnotationMark] = []
        self._selected = -1
        self._tool = "rectangle"
        self._color = ANNOTATION_PALETTE["Magenta"]
        self._label_draft = "LABEL"
        self._background = QColor("#17131d")
        self._gesture: AnnotationGesture | None = None
        self._gesture_before: tuple[list[AnnotationMark], int] | None = None
        self._undo: list[tuple[list[AnnotationMark], int]] = []
        self._redo: list[tuple[list[AnnotationMark], int]] = []
        self.setMinimumSize(480, 280)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @property
    def marks(self) -> tuple[AnnotationMark, ...]:
        """Return detached annotation values for inspection.

        Returns:
            tuple[AnnotationMark, ...]: Immutable tuple of annotation mark copies.
        """
        return tuple(mark.copy() for mark in self._marks)

    @property
    def rectangles(self) -> tuple[QRect, ...]:
        """Return compatibility rectangle geometry in current widget coordinates.

        Returns:
            tuple[QRect, ...]: Rectangle geometries mapped to widget coordinates.
        """
        image = self._image_rect()
        return tuple(
            QRect(
                round(image.x() + mark.x * image.width()),
                round(image.y() + mark.y * image.height()),
                round(mark.width * image.width()),
                round(mark.height * image.height()),
            )
            for mark in self._marks
            if mark.kind == "rectangle"
        )

    @property
    def selected_index(self) -> int:
        """Return the selected mark index, or -1 when selection is empty.

        Returns:
            int: Selected mark index or -1.
        """
        return self._selected

    @property
    def can_undo(self) -> bool:
        """Return whether an undo snapshot is available.

        Returns:
            bool: True if undo is available.
        """
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        """Return whether a redo snapshot is available.

        Returns:
            bool: True if redo is available.
        """
        return bool(self._redo)

    @property
    def has_selection(self) -> bool:
        """Return whether one live mark owns editor selection.

        Returns:
            bool: True if a mark is selected.
        """
        return 0 <= self._selected < len(self._marks)

    @property
    def selected_mark(self) -> AnnotationMark | None:
        """Return a detached selected mark for presentation synchronization.

        Returns:
            AnnotationMark | None: Selected mark copy, or None.
        """
        return self._marks[self._selected].copy() if self.has_selection else None

    def _notify_state(self) -> None:
        """Repaint and publish one coherent editor-state transition.

        Returns:
            None
        """
        self.update()
        self.stateChanged.emit()

    def set_background(self, color: str) -> None:
        """Apply the containing avatar theme to the canvas letterbox surface.

        Args:
            color (str): Color specification string.

        Returns:
            None
        """
        parsed = QColor(color)
        if not parsed.isValid():
            raise ValueError(f"Unsupported canvas background: {color}")
        self._background = parsed
        self._notify_state()

    def set_tool(self, tool: str) -> None:
        """Select one closed annotation tool.

        Args:
            tool (str): Annotation tool identifier string.

        Returns:
            None
        """
        normalized = str(tool).casefold().strip()
        if normalized not in ANNOTATION_TOOLS:
            raise ValueError(f"Unsupported annotation tool: {tool}")
        self._tool = normalized

    def set_color(self, color: str) -> None:
        """Set the drawing color while preserving palette compatibility.

        Args:
            color (str): Color specification string.

        Returns:
            None
        """
        parsed = QColor(color)
        if not parsed.isValid():
            raise ValueError(f"Unsupported annotation color: {color}")
        self._color = parsed.name()

    def apply_color(self, color: str) -> None:
        """Set the drawing color and recolor the selected mark, when present.

        Args:
            color (str): Color specification string.

        Returns:
            None
        """
        self.set_color(color)
        if 0 <= self._selected < len(self._marks):
            self._save_undo()
            self._marks[self._selected].color = self._color
            self._notify_state()

    def set_label(self, label: str) -> None:
        """Set the label draft and relabel a selected label mark.

        Args:
            label (str): Label text string.

        Returns:
            None
        """
        self._label_draft = str(label)
        if 0 <= self._selected < len(self._marks):
            mark = self._marks[self._selected]
            if mark.kind == "label" and mark.label != self._label_draft:
                self._save_undo()
                mark.label = self._label_draft
                self._notify_state()

    def add_rectangle(self, rect: QRect) -> None:
        """Append an image-clipped rectangle from widget coordinates.

        Args:
            rect (QRect): Target rectangle in widget coordinates.

        Returns:
            None
        """
        clipped = QRect(rect).normalized().intersected(self._image_rect())
        if clipped.width() <= 2 or clipped.height() <= 2:
            return
        first = self._to_normalized(clipped.topLeft())
        second = self._to_normalized(
            QPoint(clipped.x() + clipped.width(), clipped.y() + clipped.height()),
        )
        self._save_undo()
        self._marks.append(self._bounded_mark(AnnotationMark(
            "rectangle", first.x(), first.y(), second.x() - first.x(),
            second.y() - first.y(), self._color, self._next_shape_label(),
        )))
        self._notify_state()

    def delete_selected(self) -> None:
        """Delete only the selected mark and renumber geometric marks.

        Returns:
            None
        """
        if not 0 <= self._selected < len(self._marks):
            return
        self._save_undo()
        self._marks.pop(self._selected)
        self._selected = -1
        self._renumber_shapes()
        self._notify_state()

    def remove_last(self) -> None:
        """Compatibility action that removes the most recent mark.

        Returns:
            None
        """
        if not self._marks:
            return
        self._save_undo()
        self._marks.pop()
        self._selected = -1
        self._renumber_shapes()
        self._notify_state()

    def clear_annotations(self) -> None:
        """Clear all marks as one undoable editor action.

        Returns:
            None
        """
        if not self._marks:
            return
        self._save_undo()
        self._marks.clear()
        self._selected = -1
        self._notify_state()

    def undo(self) -> None:
        """Restore the previous committed annotation state.

        Returns:
            None
        """
        if not self._undo:
            return
        self._redo.append(self._snapshot())
        self._restore(self._undo.pop())

    def redo(self) -> None:
        """Restore the next annotation state after an undo.

        Returns:
            None
        """
        if not self._redo:
            return
        self._undo.append(self._snapshot())
        self._restore(self._redo.pop())

    def select_at(self, point: QPoint) -> int:
        """Select the topmost mark hit at one widget point.

        Args:
            point (QPoint): Widget coordinate point to test.

        Returns:
            int: Selected mark index or -1.
        """
        normalized = self._to_normalized(point)
        self._selected = self._hit_test(normalized) if self._image_rect().contains(point) else -1
        self._notify_state()
        return self._selected

    def move_selected(self, dx: int, dy: int) -> None:
        """Move the selected mark by a widget-pixel delta, clamped to the image.

        Args:
            dx (int): Horizontal pixel offset.
            dy (int): Vertical pixel offset.

        Returns:
            None
        """
        if not 0 <= self._selected < len(self._marks):
            return
        image = self._image_rect()
        self._save_undo()
        self._marks[self._selected] = self._translated_mark(
            self._marks[self._selected],
            dx / max(1, image.width()),
            dy / max(1, image.height()),
        )
        self._notify_state()

    def baked_pixmap(self) -> QPixmap:
        """Export source-resolution PNG content without editor selection chrome.

        Returns:
            QPixmap: Baked high-resolution QPixmap image.
        """
        if self._pixmap.isNull():
            return QPixmap()
        output = QPixmap(self._pixmap)
        painter = QPainter(output)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        target = QRectF(QPointF(0, 0), output.deviceIndependentSize())
        self._paint_marks(painter, target, show_selection=False)
        painter.end()
        return output

    def _image_rect(self) -> QRect:
        """Return the letterboxed source-image rectangle in widget coordinates.
        
        Returns:
            The source-image rectangle in widget coordinates."""
        if self._pixmap.isNull():
            return self.rect()
        size = self._pixmap.deviceIndependentSize().toSize().scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio,
        )
        return QRect(
            (self.width() - size.width()) // 2,
            (self.height() - size.height()) // 2,
            size.width(),
            size.height(),
        )

    def _to_normalized(self, point: QPoint | QPointF) -> QPointF:
        """Convert a widget point to clamped image-relative coordinates.
        
        Args:
            point: Point in widget or normalized image coordinates.
        
        Returns:
            A point clamped to normalized image coordinates."""
        image = self._image_rect()
        return QPointF(
            min(1.0, max(0.0, (point.x() - image.x()) / max(1, image.width()))),
            min(1.0, max(0.0, (point.y() - image.y()) / max(1, image.height()))),
        )

    @staticmethod
    def _point_in_target(point: QPointF, target: QRectF) -> QPointF:
        """Map one normalized point into a painter target rectangle.
        
        Args:
            point: Point in widget or normalized image coordinates.
            target: Painter rectangle receiving projected geometry.
        
        Returns:
            The mapped painter coordinate."""
        return QPointF(
            target.x() + point.x() * target.width(),
            target.y() + point.y() * target.height(),
        )

    def _mark_widget_rect(self, mark: AnnotationMark) -> QRectF:
        """Project one normalized mark into widget-space bounds.
        
        Args:
            mark: Annotation mark being measured or changed.
        
        Returns:
            The mark bounds in widget coordinates."""
        image = QRectF(self._image_rect())
        first = self._point_in_target(QPointF(mark.x, mark.y), image)
        second = self._point_in_target(QPointF(mark.x + mark.width, mark.y + mark.height), image)
        return QRectF(first, second).normalized()

    def _snapshot(self) -> tuple[list[AnnotationMark], int]:
        """Capture detached marks and selection for history.
        
        Returns:
            A detached mark list and selected index."""
        return ([mark.copy() for mark in self._marks], self._selected)

    def _restore(self, state: tuple[list[AnnotationMark], int]) -> None:
        """Restore a previously captured editor state.
        
        Args:
            state: Mark list and selected index captured for history.
        
        Returns:
            None."""
        marks, selected = state
        self._marks = [mark.copy() for mark in marks]
        self._selected = selected if selected < len(self._marks) else -1
        self._notify_state()

    def _save_undo(self) -> None:
        """Append the current state to undo history and clear redo history.
        
        Returns:
            None."""
        self._undo.append(self._snapshot())
        self._redo.clear()

    def _next_shape_label(self) -> str:
        """Return the next numeric label for a geometric mark.
        
        Returns:
            The next numeric shape label."""
        return str(sum(mark.kind != "label" for mark in self._marks) + 1)

    def _renumber_shapes(self) -> None:
        """Renumber geometric marks after a deletion.
        
        Returns:
            None."""
        number = 0
        for mark in self._marks:
            if mark.kind != "label":
                number += 1
                mark.label = str(number)

    @staticmethod
    def _bounds(mark: AnnotationMark) -> tuple[float, float, float, float]:
        """Return normalized extents for rectangular or point-based geometry.
        
        Args:
            mark: Annotation mark being measured or changed.
        
        Returns:
            Left, top, right, and bottom normalized coordinates."""
        if mark.points:
            xs = [point.x() for point in mark.points]
            ys = [point.y() for point in mark.points]
            return min(xs), min(ys), max(xs), max(ys)
        x2, y2 = mark.x + mark.width, mark.y + mark.height
        return min(mark.x, x2), min(mark.y, y2), max(mark.x, x2), max(mark.y, y2)

    def _bounded_mark(self, mark: AnnotationMark) -> AnnotationMark:
        """Translate a mark enough to keep its bounds inside the image.
        
        Args:
            mark: Annotation mark being measured or changed.
        
        Returns:
            A detached mark constrained to the image."""
        left, top, right, bottom = self._bounds(mark)
        dx = max(-left, min(0.0, 1.0 - right))
        dy = max(-top, min(0.0, 1.0 - bottom))
        return self._translated_raw(mark, dx, dy)

    def _translated_mark(self, mark: AnnotationMark, dx: float, dy: float) -> AnnotationMark:
        """Translate a mark while clamping its normalized displacement.
        
        Args:
            mark: Annotation mark being measured or changed.
            dx: Normalized horizontal displacement.
            dy: Normalized vertical displacement.
        
        Returns:
            A detached mark with a safe displacement."""
        left, top, right, bottom = self._bounds(mark)
        safe_dx = min(max(dx, -left), 1.0 - right)
        safe_dy = min(max(dy, -top), 1.0 - bottom)
        return self._translated_raw(mark, safe_dx, safe_dy)

    @staticmethod
    def _translated_raw(mark: AnnotationMark, dx: float, dy: float) -> AnnotationMark:
        """Translate mark coordinates without boundary constraints.
        
        Args:
            mark: Annotation mark being measured or changed.
            dx: Normalized horizontal displacement.
            dy: Normalized vertical displacement.
        
        Returns:
            A detached translated mark."""
        return replace(
            mark,
            x=mark.x + dx,
            y=mark.y + dy,
            points=tuple(QPointF(point.x() + dx, point.y() + dy) for point in mark.points),
        )

    def _hit_test(self, point: QPointF) -> int:
        """Return the topmost mark hit by a normalized point.
        
        Args:
            point: Point in widget or normalized image coordinates.
        
        Returns:
            The mark index, or -1 when no mark is hit."""
        image = self._image_rect()
        tolerance = 10 / max(1, min(image.width(), image.height()))
        for index in range(len(self._marks) - 1, -1, -1):
            mark = self._marks[index]
            if mark.kind == "label":
                width = max(tolerance * 2, len(mark.label) * 10 / max(1, image.width()))
                height = max(tolerance * 2, 24 / max(1, image.height()))
                if QRectF(mark.x - tolerance, mark.y - tolerance, width + tolerance, height + tolerance).contains(point):
                    return index
            elif mark.kind in {"arrow", "path"}:
                points = mark.points or (QPointF(mark.x, mark.y), QPointF(mark.x + mark.width, mark.y + mark.height))
                if any(self._distance_to_segment(point, a, b) <= tolerance for a, b in zip(points, points[1:])):
                    return index
            else:
                left, top, right, bottom = self._bounds(mark)
                outer = QRectF(left - tolerance, top - tolerance, right - left + tolerance * 2, bottom - top + tolerance * 2)
                inner = QRectF(left + tolerance, top + tolerance, max(0.0, right - left - tolerance * 2), max(0.0, bottom - top - tolerance * 2))
                if outer.contains(point) and not inner.contains(point):
                    return index
        return -1

    @staticmethod
    def _distance_to_segment(point: QPointF, start: QPointF, end: QPointF) -> float:
        """Measure the shortest distance from a point to a segment.
        
        Args:
            point: Point in widget or normalized image coordinates.
            start: Segment start point.
            end: Segment end point.
        
        Returns:
            The Euclidean distance in normalized coordinates."""
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length_sq = dx * dx + dy * dy
        if length_sq == 0:
            return math.hypot(point.x() - start.x(), point.y() - start.y())
        projection = (
            (point.x() - start.x()) * dx
            + (point.y() - start.y()) * dy
        )
        ratio = max(0.0, min(1.0, projection / length_sq))
        return math.hypot(point.x() - start.x() - ratio * dx, point.y() - start.y() - ratio * dy)

    def paintEvent(self, event) -> None:  # noqa: N802
        """Paint the themed canvas, source image, marks, and selection overlay.
        
        Args:
            event: Qt input event supplied by the widget system.
        
        Returns:
            None."""
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._background)
        image = self._image_rect()
        if not self._pixmap.isNull():
            painter.drawPixmap(image, self._pixmap)
        self._paint_marks(painter, QRectF(image), show_selection=True)
        painter.end()

    def _paint_marks(self, painter: QPainter, target: QRectF, show_selection: bool) -> None:
        """Paint normalized marks into a target rectangle.
        
        Args:
            painter: Active Qt painter.
            target: Painter rectangle receiving projected geometry.
            show_selection: Whether to paint the selected-mark outline.
        
        Returns:
            None."""
        stroke = max(3.0, min(target.width(), target.height()) * 0.004)
        font_size = max(14.0, target.width() * 0.016)
        for index, mark in enumerate(self._marks):
            color = QColor(mark.color)
            pen = QPen(
                color,
                stroke,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            start = self._point_in_target(QPointF(mark.x, mark.y), target)
            end = self._point_in_target(QPointF(mark.x + mark.width, mark.y + mark.height), target)
            if mark.kind == "label":
                font = painter.font()
                font.setBold(True)
                font.setPixelSize(round(font_size))
                painter.setFont(font)
                painter.setPen(color)
                painter.drawText(start, mark.label)
            elif mark.kind == "path":
                path = QPainterPath()
                if mark.points:
                    first = self._point_in_target(mark.points[0], target)
                    path.moveTo(first)
                    for point in mark.points[1:]:
                        path.lineTo(self._point_in_target(point, target))
                painter.drawPath(path)
            elif mark.kind == "arrow":
                painter.drawLine(start, end)
                angle = math.atan2(end.y() - start.y(), end.x() - start.x())
                size = max(12.0, target.width() * 0.015)
                head = QPolygonF([
                    end,
                    QPointF(end.x() - size * math.cos(angle - 0.45), end.y() - size * math.sin(angle - 0.45)),
                    QPointF(end.x() - size * math.cos(angle + 0.45), end.y() - size * math.sin(angle + 0.45)),
                ])
                painter.setBrush(color)
                painter.drawPolygon(head)
                painter.setBrush(Qt.BrushStyle.NoBrush)
            else:
                painter.drawRect(QRectF(start, end).normalized())
            if mark.kind != "label" and mark.label:
                font = painter.font()
                font.setBold(True)
                font.setPixelSize(round(font_size))
                painter.setFont(font)
                painter.setPen(color)
                painter.drawText(end - QPointF(stroke * 2, stroke * 2), mark.label)
            if show_selection and index == self._selected:
                selection = self._selection_rect(mark, target).adjusted(-5, -5, 5, 5)
                select_pen = QPen(QColor("white"), 2, Qt.PenStyle.DashLine)
                painter.setPen(select_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(selection)

    def _selection_rect(self, mark: AnnotationMark, target: QRectF) -> QRectF:
        """Return the selection rectangle for one projected mark.
        
        Args:
            mark: Annotation mark being measured or changed.
            target: Painter rectangle receiving projected geometry.
        
        Returns:
            None."""
        left, top, right, bottom = self._bounds(mark)
        first = self._point_in_target(QPointF(left, top), target)
        second = self._point_in_target(QPointF(right, bottom), target)
        if mark.kind == "label":
            second = first + QPointF(max(30, len(mark.label) * 10), 24)
        return QRectF(first, second).normalized()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Start selection, label creation, or a drawing gesture.
        
        Args:
            event: Qt input event supplied by the widget system.
        
        Returns:
            None."""
        point = event.position().toPoint()
        if event.button() != Qt.MouseButton.LeftButton or not self._image_rect().contains(point):
            return
        normalized = self._to_normalized(point)
        hit = self._hit_test(normalized)
        self._gesture_before = self._snapshot()
        if hit >= 0:
            self._selected = hit
            self._gesture = AnnotationGesture("drag", normalized, hit, self._marks[hit].copy())
        elif self._tool == "label":
            self._marks.append(AnnotationMark("label", normalized.x(), normalized.y(), 0, 0, self._color, self._label_draft or "LABEL"))
            self._selected = len(self._marks) - 1
            self._commit_gesture_history()
        else:
            points = (QPointF(normalized),) if self._tool == "path" else ()
            self._marks.append(AnnotationMark(self._tool, normalized.x(), normalized.y(), 0, 0, self._color, self._next_shape_label(), points))
            self._selected = len(self._marks) - 1
            self._gesture = AnnotationGesture("draw", normalized, self._selected)
        self._notify_state()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Update the active drag or drawing gesture.
        
        Args:
            event: Qt input event supplied by the widget system.
        
        Returns:
            None."""
        if self._gesture is None:
            return
        current = self._to_normalized(event.position())
        gesture = self._gesture
        if gesture.mode == "drag" and gesture.original is not None:
            self._marks[gesture.index] = self._translated_mark(
                gesture.original,
                current.x() - gesture.start.x(),
                current.y() - gesture.start.y(),
            )
        else:
            mark = self._marks[gesture.index]
            if mark.kind == "path":
                mark.points = (*mark.points, QPointF(current))
                mark.width = current.x() - mark.x
                mark.height = current.y() - mark.y
            else:
                mark.width = current.x() - gesture.start.x()
                mark.height = current.y() - gesture.start.y()
        self._notify_state()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Commit or discard the active gesture.
        
        Args:
            event: Qt input event supplied by the widget system.
        
        Returns:
            None."""
        if self._gesture is None or event.button() != Qt.MouseButton.LeftButton:
            return
        gesture = self._gesture
        if gesture.mode == "draw":
            mark = self._marks[gesture.index]
            valid = len(mark.points) > 2 if mark.kind == "path" else math.hypot(mark.width, mark.height) > 0.01
            if not valid:
                self._marks.pop(gesture.index)
                self._selected = -1
                self._gesture_before = None
            else:
                if mark.kind == "rectangle":
                    left, top, right, bottom = self._bounds(mark)
                    mark.x, mark.y, mark.width, mark.height = left, top, right - left, bottom - top
                self._commit_gesture_history()
        else:
            self._commit_gesture_history()
        self._gesture = None
        self._notify_state()

    def _commit_gesture_history(self) -> None:
        """Commit the active gesture as one undoable transition.
        
        Returns:
            None."""
        if self._gesture_before is not None:
            before_marks, before_selected = self._gesture_before
            current_marks, current_selected = self._snapshot()
            changed = before_selected != current_selected or before_marks != current_marks
            if changed:
                self._undo.append((before_marks, before_selected))
                self._redo.clear()
        self._gesture_before = None
