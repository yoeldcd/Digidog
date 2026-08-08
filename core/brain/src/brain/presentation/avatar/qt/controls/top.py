# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Painter for the top focus, message, and processing zone."""
from __future__ import annotations

import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QConicalGradient,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)

from brain.presentation.avatar.qt.controls.geometry import (
    backlog_geometry,
    capture_geometry,
    chrome_geometry,
    pin_fill_color,
)


class QtTopControlsMixin:
    """Painter mixin for the top focus, message, pin, and processing controls."""

    def _processing_center(self) -> QPointF:
        """Return the message-control center that owns processing cancellation.

        Returns:
            QPointF: Center point of the message control.
        """
        _pin_bounds, message_bounds, _grip = chrome_geometry(self.width(), self.height())
        return message_bounds.center()

    def _paint_processing(self, painter: QPainter) -> None:
        """Trace the message-bubble silhouette with an animated six-color border.

        Args:
            painter (QPainter): Active painter target.

        Returns:
            None.
        """
        if not self.processing:
            return

        _pin_bounds, message_bounds, _grip = chrome_geometry(self.width(), self.height())
        bubble = QPainterPath()
        bubble.addRoundedRect(QRectF(-11, -9, 22, 15), 6, 6)

        tail = QPainterPath()
        tail.moveTo(3, 5)
        tail.lineTo(1, 12)
        tail.lineTo(8, 5)
        tail.closeSubpath()

        silhouette = bubble.united(tail)
        colors = ("#3b82f6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#ec4899")
        border_gradient = QConicalGradient(QPointF(0, 0), -(self.processing_frame * 8))

        for index, color in enumerate(colors):
            border_gradient.setColorAt(index / len(colors), QColor(color))
        border_gradient.setColorAt(1.0, QColor(colors[0]))

        scale = message_bounds.width() / 42
        painter.save()
        painter.translate(message_bounds.center())
        painter.scale(scale, scale)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border_gradient, 4.2 / scale, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(silhouette)
        painter.restore()

    def _paint_processing_emotion(self, painter: QPainter, center: QPointF) -> None:
        """Paint a raster-stable emoji pictogram for the active speak emotion.

        Args:
            painter (QPainter): Active painter target.
            center (QPointF): Center point of target control area.

        Returns:
            None.
        """
        emotion = self.processing_emotion
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#ffffff"), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))

        if emotion in {"focused", "determined", "working", "coding", "debugging"}:
            painter.drawEllipse(center, 7, 7)
            painter.drawEllipse(center, 3.5, 3.5)
            painter.setBrush(QColor("#ffffff"))
            painter.drawEllipse(center, 1.3, 1.3)
        elif emotion in {"love", "loved", "tender", "caring", "adoring", "devoted"}:
            heart = QPainterPath(QPointF(center.x(), center.y() + 6))
            heart.cubicTo(center.x() - 11, center.y(), center.x() - 6, center.y() - 8, center.x(), center.y() - 3)
            heart.cubicTo(center.x() + 6, center.y() - 8, center.x() + 11, center.y(), center.x(), center.y() + 6)
            painter.setBrush(QColor("#ff6fae"))
            painter.drawPath(heart)
        elif emotion in {"angry", "alert", "frustrated", "surprised", "shocked"}:
            triangle = QPolygonF((
                QPointF(center.x(), center.y() - 8),
                QPointF(center.x() - 8, center.y() + 7),
                QPointF(center.x() + 8, center.y() + 7),
            ))
            painter.setBrush(QColor("#f59e0b"))
            painter.drawPolygon(triangle)
            painter.setPen(QPen(QColor("#1f1420"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(center.x(), center.y() - 3), QPointF(center.x(), center.y() + 2))
            painter.drawPoint(QPointF(center.x(), center.y() + 4.5))
        else:
            painter.drawEllipse(center, 8, 8)
            painter.drawPoint(QPointF(center.x() - 3, center.y() - 2))
            painter.drawPoint(QPointF(center.x() + 3, center.y() - 2))
            mouth_y = center.y() + (4 if emotion in {"sad", "melancholic", "lonely"} else 1)
            mouth = QPainterPath(QPointF(center.x() - 4, mouth_y))
            control_y = mouth_y - 4 if emotion in {"sad", "melancholic", "lonely"} else mouth_y + 4
            mouth.quadTo(center.x(), control_y, center.x() + 4, mouth_y)
            painter.drawPath(mouth)

        painter.restore()

    def _paint_pin(self, painter: QPainter) -> None:
        """Paint the window pin toggle button on the control overlay.

        Args:
            painter (QPainter): Active painter target.

        Returns:
            None.
        """
        bounds, _message, _grip = chrome_geometry(self.width(), self.height())
        # Simplified contour traced from the original 79x79 control artwork.
        # Keeping its source coordinates preserves the former proportions.
        points = (
            (24, 58), (32, 50), (32, 47), (25, 41), (25, 38),
            (28, 36), (38, 36), (45, 29), (46, 21), (49, 21),
            (63, 35), (62, 38), (56, 38), (48, 45), (46, 58),
            (42, 58), (36, 52), (32, 53), (25, 60), (24, 58),
        )
        path = QPainterPath(QPointF(*points[0]))

        for point in points[1:]:
            path.lineTo(QPointF(*point))
        path.closeSubpath()

        painter.save()
        painter.translate(bounds.topLeft())
        scale = bounds.width() / 79
        painter.scale(scale, scale)

        fill = pin_fill_color(self.pinned)
        outline = QColor("#dcecff") if self.pinned else QColor("#75adff")
        painter.setBrush(fill)
        painter.setPen(QPen(outline, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)
        painter.restore()

    def _paint_backlog(self, painter: QPainter) -> None:
        """Paint a compact clock below the message control.

        Args:
            painter (QPainter): Active painter target.

        Returns:
            None.
        """
        bounds = backlog_geometry(self.width(), self.height())
        center = bounds.center()
        radius = bounds.width() / 2 - 2

        painter.save()
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, radius, radius)
        painter.setPen(
            QPen(
                QColor("#123b78"),
                2.2,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            ),
        )
        painter.drawLine(center, QPointF(center.x(), center.y() - radius * 0.48))
        painter.drawLine(
            center,
            QPointF(center.x() + radius * 0.42, center.y() + radius * 0.18),
        )
        painter.restore()

    def _paint_capture(self, painter: QPainter) -> None:
        """Paint the picture action that starts screenshot annotation."""
        bounds = capture_geometry(self.width(), self.height())
        picture_bounds = bounds.adjusted(3, 4, -3, -4)
        mountain = QPainterPath(
            QPointF(picture_bounds.left() + 2, picture_bounds.bottom() - 2),
        )
        mountain.lineTo(
            QPointF(picture_bounds.center().x() - 1, picture_bounds.center().y()),
        )
        mountain.lineTo(
            QPointF(
                picture_bounds.center().x() + 2,
                picture_bounds.center().y() + 2,
            ),
        )
        mountain.lineTo(
            QPointF(picture_bounds.right() - 2, picture_bounds.top() + 7),
        )

        painter.save()
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(QColor("#123b78"), 1.8))
        painter.drawRoundedRect(picture_bounds, 2, 2)
        painter.setBrush(QColor("#83b7ef"))
        painter.drawEllipse(
            QPointF(picture_bounds.right() - 5, picture_bounds.top() + 5),
            1.6,
            1.6,
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(mountain)
        painter.restore()

    def _paint_show_message(self, painter: QPainter) -> None:
        """Paint a filled message bubble with its queued-item count inside.

        Args:
            painter (QPainter): Active painter target.

        Returns:
            None.
        """
        _pin, bounds, _grip = chrome_geometry(self.width(), self.height())
        bubble_bounds = QRectF(-11, -9, 22, 15)

        painter.save()
        painter.translate(bounds.center())
        scale = bounds.width() / 42
        painter.scale(scale, scale)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(bubble_bounds, 6, 6)

        tail = QPainterPath()
        tail.moveTo(3, 5)
        tail.lineTo(1, 12)
        tail.lineTo(8, 5)
        tail.closeSubpath()
        painter.drawPath(tail)

        if self.queue_depth:
            buffer_text = "99+" if self.queue_depth > 99 else str(self.queue_depth)
            font_size = 7 if self.queue_depth > 99 else 10
            painter.setPen(QColor("#e32636"))
            painter.setFont(QFont("Segoe UI", font_size, QFont.Weight.Bold))
            painter.drawText(bubble_bounds, Qt.AlignmentFlag.AlignCenter, buffer_text)

        painter.restore()

    def _paint_passive_queue(self, painter: QPainter) -> None:
        """Paint the queue count without the hover-only bubble body or tail."""
        if not self.queue_depth:
            return

        _pin, bounds, _grip = chrome_geometry(self.width(), self.height())
        buffer_text = "99+" if self.queue_depth > 99 else str(self.queue_depth)
        font_size = 9 if self.queue_depth > 99 else 12

        painter.save()
        painter.setPen(QColor("#e32636"))
        painter.setFont(QFont("Segoe UI", font_size, QFont.Weight.Bold))
        painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, buffer_text)
        painter.restore()

