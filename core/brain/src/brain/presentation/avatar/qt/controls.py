# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Custom-painted Qt controls faithful to the original avatar overlay."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget


def playback_geometry(width: int, height: int) -> tuple[QPointF, int]:
    radius = max(21, min(44, round(width * .13)))
    return QPointF(width / 2, height - radius - max(6, round(height * .02))), radius


def quota_geometry(width: int, height: int) -> tuple[QPointF, QPointF, int]:
    play_center, play_radius = playback_geometry(width, height)
    former_radius = max(16, min(34, round(width * .10)))
    radius = max(13, round(former_radius * .78))
    reset_height = max(9, round(radius * .50))
    center_y = play_center.y() + play_radius - radius - reset_height
    offset = play_radius + radius + max(4, round(width * .025))
    return QPointF(width / 2 - offset, center_y), QPointF(width / 2 + offset, center_y), radius


def mute_geometry(width: int, height: int) -> tuple[QPointF, int]:
    radius = max(10, min(16, round(width * .048)))
    padding = max(5, round(width * .025))
    return QPointF(padding + radius, height - padding - radius), radius


def chrome_geometry(width: int, height: int) -> tuple[QRectF, QRectF, QRectF]:
    size = max(32, min(46, round(width * .16)))
    grip_size = max(22, min(38, round(width * .12)))
    pad = max(4, round(width * .025))
    return (
        QRectF(pad, pad, size, size),
        QRectF(width - pad - size, pad, size, size),
        QRectF(width - grip_size, height - grip_size, grip_size, grip_size),
    )


def quota_color(used_percent: int) -> QColor:
    if used_percent >= 75:
        return QColor("#ff4f64")
    if used_percent >= 50:
        return QColor("#ff982f")
    if used_percent >= 25:
        return QColor("#f1d447")
    return QColor("#36c978")


def pin_fill_color(pinned: bool) -> QColor:
    return QColor("#3b8cff") if pinned else QColor("#f8fbff")


class QtAvatarControls(QWidget):
    """One transparent overlay owning custom playback, quota, and mute hitboxes."""

    def __init__(self, parent: QWidget, on_playback: Callable[[], None], on_mute: Callable[[], None],
                 on_pin: Callable[[bool], None], on_avatar: Callable[[], None], on_quota: Callable[[], None],
                 on_show_message: Callable[[], None]) -> None:
        super().__init__(parent)
        self.on_playback = on_playback
        self.on_mute = on_mute
        self.on_pin = on_pin
        self.on_avatar = on_avatar
        self.on_quota = on_quota
        self.on_show_message = on_show_message
        self.playing = False
        self.muted = False
        self.pinned = True
        self.quotas: tuple[int, int] | None = None
        self.quota_resets: tuple[str, str] = ("", "")
        self._hover_corner = ""
        self._resize_origin: tuple[str, QPoint, QRect] | None = None
        self._drag_origin: tuple[QPoint, QPoint] | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

    def set_state(self, playing: bool, muted: bool) -> None:
        self.playing, self.muted = playing, muted
        self.update()

    def set_quotas(self, five_hour: int, weekly: int, five_reset: str = "", weekly_reset: str = "") -> None:
        self.quotas = (five_hour, weekly)
        self.quota_resets = (five_reset, weekly_reset)
        self.update()

    @staticmethod
    def _inside(point: QPointF, center: QPointF, radius: int) -> bool:
        return (point.x() - center.x()) ** 2 + (point.y() - center.y()) ** 2 <= radius ** 2

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        point = event.position()
        play_center, play_radius = playback_geometry(self.width(), self.height())
        mute_center, mute_radius = mute_geometry(self.width(), self.height())
        pin_bounds, message_bounds, grip_bounds = chrome_geometry(self.width(), self.height())
        quota_left, quota_right, quota_radius = quota_geometry(self.width(), self.height())
        if self._inside(point, play_center, play_radius):
            self.on_playback()
            event.accept()
            return
        if self._inside(point, mute_center, mute_radius):
            self.on_mute()
            event.accept()
            return
        if self._inside(point, quota_left, quota_radius) or self._inside(point, quota_right, quota_radius):
            self.on_quota()
            event.accept()
            return
        if message_bounds.contains(point):
            self.on_show_message()
            event.accept()
            return
        if pin_bounds.contains(point):
            self.pinned = not self.pinned
            self.on_pin(self.pinned)
            self.update()
            event.accept()
            return
        # Interactive controls own overlapping pixels. Resize corners are the
        # fallback hit target, so the lower-left affordance cannot steal mute.
        if grip_bounds.contains(point):
            self._resize_origin = ("se", event.globalPosition().toPoint(), self.parentWidget().geometry())
            self.grabMouse()
            event.accept()
            return
        self._drag_origin = (event.globalPosition().toPoint(), self.parentWidget().pos())
        event.accept()

    def _nearest_corner(self, point: QPointF) -> str:
        _pin, _message, grip = chrome_geometry(self.width(), self.height())
        return "se" if grip.contains(point) else ""

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._resize_origin:
            corner, pointer, geometry = self._resize_origin
            delta = event.globalPosition().toPoint() - pointer
            minimum = self.parentWidget().minimumSize()
            width = max(minimum.width(), geometry.width() + delta.x())
            height = round(width * 4 / 3)
            if height < minimum.height():
                height = minimum.height()
                width = round(height * 3 / 4)
            self.parentWidget().setGeometry(geometry.left(), geometry.top(), width, height)
        elif self._drag_origin:
            pointer, origin = self._drag_origin
            self.parentWidget().move(origin + event.globalPosition().toPoint() - pointer)
            updater = getattr(self.parentWidget(), "_update_tail", None)
            if updater:
                updater()
        else:
            self._hover_corner = self._nearest_corner(event.position())
            cursor = Qt.CursorShape.SizeFDiagCursor if self._hover_corner in {"nw", "se"} else Qt.CursorShape.SizeBDiagCursor if self._hover_corner else Qt.CursorShape.ArrowCursor
            self.setCursor(cursor)
            self.update()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._drag_origin:
            pointer, _origin = self._drag_origin
            if (event.globalPosition().toPoint() - pointer).manhattanLength() <= 4:
                self.on_avatar()
        was_resizing = self._resize_origin is not None
        self._resize_origin = None
        self._drag_origin = None
        if was_resizing:
            self.releaseMouse()
        super().mouseReleaseEvent(event)

    def sync_pointer(self, global_pointer: QPoint) -> None:
        """Update the nearest resize affordance even over transparent pixels."""
        local = self.mapFromGlobal(global_pointer)
        corner = self._nearest_corner(QPointF(local)) if self.rect().contains(local) else ""
        if corner != self._hover_corner:
            self._hover_corner = corner
            self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._hover_corner = ""
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_quotas(painter)
        self._paint_playback(painter)
        self._paint_mute(painter)
        self._paint_pin(painter)
        self._paint_show_message(painter)
        self._paint_resize_grip(painter)
        painter.end()

    def _paint_pin(self, painter: QPainter) -> None:
        bounds, _message, _grip = chrome_geometry(self.width(), self.height())
        painter.fillRect(bounds, QColor(16, 24, 32, 220))
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

    def _paint_show_message(self, painter: QPainter) -> None:
        _pin, bounds, _grip = chrome_geometry(self.width(), self.height())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(16, 24, 32, 220))
        painter.drawRect(bounds)
        painter.save()
        painter.translate(bounds.center())
        scale = bounds.width() / 42
        painter.scale(scale, scale)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#f8fbff"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawRoundedRect(QRectF(-11, -9, 22, 15), 6, 6)
        tail = QPainterPath()
        tail.moveTo(3, 6)
        tail.lineTo(1, 12)
        tail.lineTo(8, 6)
        painter.drawPath(tail)
        painter.restore()

    def _paint_resize_grip(self, painter: QPainter) -> None:
        _pin, _message, bounds = chrome_geometry(self.width(), self.height())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(16, 24, 32, 220))
        painter.drawRect(bounds)
        inset = max(5, round(bounds.width() * .25))
        painter.setBrush(QColor("#f8fbff"))
        painter.drawPolygon(QPolygonF([
            QPointF(bounds.right() - inset, bounds.bottom() - inset * 2.5),
            QPointF(bounds.right() - inset, bounds.bottom() - inset),
            QPointF(bounds.right() - inset * 2.5, bounds.bottom() - inset),
        ]))

    def _paint_playback(self, painter: QPainter) -> None:
        center, radius = playback_geometry(self.width(), self.height())
        painter.setPen(QPen(QColor("#3b8cff"), 3))
        painter.setBrush(QColor("#123b78"))
        painter.drawEllipse(center, radius, radius)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("white"))
        if self.playing:
            bar_width, bar_height = max(4, round(radius * .22)), round(radius * .9)
            painter.drawRoundedRect(QRectF(center.x() - radius * .38, center.y() - bar_height / 2, bar_width, bar_height), 2, 2)
            painter.drawRoundedRect(QRectF(center.x() + radius * .18, center.y() - bar_height / 2, bar_width, bar_height), 2, 2)
        else:
            painter.drawPolygon(QPolygonF([
                QPointF(center.x() - radius * .28, center.y() - radius * .55),
                QPointF(center.x() - radius * .28, center.y() + radius * .55),
                QPointF(center.x() + radius * .48, center.y()),
            ]))

    def _paint_mute(self, painter: QPainter) -> None:
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
        if self.muted:
            painter.setPen(QPen(QColor("#ff6f91"), max(2, round(radius * .16))))
            painter.drawLine(QPointF(center.x() - radius * .55, center.y() - radius * .55), QPointF(center.x() + radius * .55, center.y() + radius * .55))
        else:
            painter.setPen(QPen(QColor("white"), max(2, round(radius * .12))))
            painter.drawArc(QRectF(center.x() - radius * .05, center.y() - radius * .55, radius * .75, radius * 1.1), -55 * 16, 110 * 16)

    def _paint_quotas(self, painter: QPainter) -> None:
        if self.quotas is None:
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
