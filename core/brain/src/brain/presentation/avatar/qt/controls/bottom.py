# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Painter for bottom playback, mute, queue, and quota meters."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF

from brain.presentation.avatar.qt.controls.geometry import (
    mute_geometry, playback_geometry, quota_color, quota_geometry,
)


class QtBottomControlsMixin:
    """Painter mixin for bottom playback, mute, queue, and quota meters."""

    def _paint_playback(self, painter: QPainter) -> None:
        """Paint play/pause control button on the control overlay.

        Args:
            painter (QPainter): Active painter target.

        Returns:
            None.
        """
        center, radius = playback_geometry(self.width(), self.height())
        painter.setPen(QPen(QColor("#3b8cff"), 3))
        painter.setBrush(QColor("#123b78"))
        painter.drawEllipse(center, radius, radius)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("white"))

        if self.playing:
            side = radius * .82
            painter.drawRoundedRect(
                QRectF(center.x() - side / 2, center.y() - side / 2, side, side),
                3,
                3,
            )
        else:
            painter.drawPolygon(QPolygonF([
                QPointF(center.x() - radius * .28, center.y() - radius * .55),
                QPointF(center.x() - radius * .28, center.y() + radius * .55),
                QPointF(center.x() + radius * .48, center.y()),
            ]))

    def _paint_mute(self, painter: QPainter) -> None:
        """Paint mute toggle control button on the control overlay.

        Args:
            painter (QPainter): Active painter target.

        Returns:
            None.
        """
        center, radius = mute_geometry(self.width(), self.height())
        painter.setPen(QPen(QColor("#3b8cff"), max(2, round(radius * .15))))
        painter.setBrush(QColor(18, 59, 120, 190))
        painter.drawEllipse(center, radius, radius)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("white"))
        painter.drawRect(QRectF(center.x() - radius * .5, center.y() - radius * .25, radius * .28, radius * .5))
        painter.drawPolygon(QPolygonF([
            QPointF(center.x() - radius * .22, center.y() - radius * .25),
            QPointF(center.x() + radius * .18, center.y() - radius * .48),
            QPointF(center.x() + radius * .18, center.y() + radius * .48),
            QPointF(center.x() - radius * .22, center.y() + radius * .25),
        ]))

        if self.mute_mode != "off":
            painter.setPen(QPen(QColor("#ff304f"), max(2, round(radius * .16))))
            painter.drawLine(
                QPointF(center.x() - radius * .55, center.y() - radius * .55),
                QPointF(center.x() + radius * .55, center.y() + radius * .55),
            )
            if self.mute_mode == "total":
                painter.drawLine(
                    QPointF(center.x() + radius * .55, center.y() - radius * .55),
                    QPointF(center.x() - radius * .55, center.y() + radius * .55),
                )
        else:
            painter.setPen(QPen(QColor("white"), max(2, round(radius * .12))))
            painter.drawArc(QRectF(center.x() - radius * .05, center.y() - radius * .55, radius * .75, radius * 1.1), -55 * 16, 110 * 16)

    def _paint_quotas(self, painter: QPainter) -> None:
        """Paint quota usage rings and reset timers.

        Args:
            painter (QPainter): Active painter target.

        Returns:
            None.
        """
        if self.quotas is None or (self.quota_refreshing and not self.quota_blink_visible):
            return

        left, right, radius = quota_geometry(self.width(), self.height())
        ring_width = max(2, round(radius * .20))

        for index, (label, used, center) in enumerate(zip(("5h", "7d"), self.quotas, (left, right))):
            bounds = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
            painter.setPen(QPen(QColor("#315078"), ring_width))
            painter.setBrush(QColor("#101820"))
            painter.drawEllipse(bounds)
            painter.setPen(QPen(quota_color(used), ring_width))
            painter.drawArc(bounds, 90 * 16, -round(360 * (100 - used) / 100) * 16)
            painter.setPen(QColor("white"))
            painter.setFont(QFont("Segoe UI", max(8, round(radius * .56)), QFont.Weight.Bold))
            painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, f"{100 - used}%")
            painter.setPen(QColor("#a9c8f7"))
            painter.setFont(QFont("Segoe UI", max(9, round(radius * .62)), QFont.Weight.Bold))
            painter.drawText(QRectF(center.x() - radius, center.y() - radius * 2.25, radius * 2, radius), Qt.AlignmentFlag.AlignCenter, label)

            reset = self.quota_resets[index]
            if reset:
                painter.setFont(QFont("Segoe UI", max(7, round(radius * .42))))
                painter.drawText(QRectF(center.x() - radius * 1.6, center.y() + radius, radius * 3.2, radius), Qt.AlignmentFlag.AlignCenter, reset)

