# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Center avatar hit area and resize interaction adapter."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QCursor, QPainter, QPen, QPolygonF

from brain.presentation.avatar.qt.controls.geometry import (
    backlog_geometry,
    capture_geometry,
    chrome_geometry,
    mute_geometry,
    playback_geometry,
    quota_geometry,
)


class QtCenterControlsMixin:
    """Center avatar hit area, control dispatch, and resize interaction adapter."""

    @staticmethod
    def _inside(point: QPointF, center: QPointF, radius: int) -> bool:
        """Check whether a point lies within a circular target region.

        Args:
            point (QPointF): Tested point coordinates.
            center (QPointF): Center point of target circle.
            radius (int): Target circle radius.

        Returns:
            bool: True if point is inside or on the circle boundary.
        """
        return (point.x() - center.x()) ** 2 + (point.y() - center.y()) ** 2 <= radius ** 2

    def mousePressEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Dispatch overlay click, pin, resize, and drag interactions.

        Args:
            event (object): Qt mouse-press event.

        Returns:
            None.
        """
        point = event.position()
        play_center, play_radius = playback_geometry(self.width(), self.height())
        mute_center, mute_radius = mute_geometry(self.width(), self.height())
        pin_bounds, message_bounds, grip_bounds = chrome_geometry(self.width(), self.height())
        backlog_bounds = backlog_geometry(self.width(), self.height())
        capture_bounds = capture_geometry(self.width(), self.height())
        quota_left, quota_right, quota_radius = quota_geometry(self.width(), self.height())

        if self.processing and self._inside(point, self._processing_center(), 12):
            self.on_cancel_processing()
            event.accept()
            return

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

        if backlog_bounds.contains(point):
            self.on_backlog()
            event.accept()
            return

        if capture_bounds.contains(point):
            self.on_capture()
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
        """Resolve nearest resize corner code for a point inside control bounds.

        Args:
            point (QPointF): Local point coordinates.

        Returns:
            str: "se" if inside grip bounds, else empty string.
        """
        _pin, _message, grip = chrome_geometry(self.width(), self.height())
        return "se" if grip.contains(point) else ""

    def mouseMoveEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Move or resize the parent window from an overlay drag.

        Args:
            event (object): Qt mouse-move event.

        Returns:
            None.
        """
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
            cursor = (
                Qt.CursorShape.SizeFDiagCursor if self._hover_corner in {"nw", "se"}
                else Qt.CursorShape.SizeBDiagCursor if self._hover_corner
                else Qt.CursorShape.ArrowCursor
            )
            self.setCursor(cursor)
            self.update()

        event.accept()

    def mouseReleaseEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Finish drag or resize interaction and dispatch avatar clicks.

        Args:
            event (object): Qt mouse-release event.

        Returns:
            None.
        """
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
        """Update resize affordance even over transparent pixels.

        Args:
            global_pointer (QPoint): Current global mouse position.

        Returns:
            None.
        """
        local = self.mapFromGlobal(global_pointer)
        corner = self._nearest_corner(QPointF(local)) if self.rect().contains(local) else ""

        if corner != self._hover_corner:
            self._hover_corner = corner
            self.update()

    def leaveEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Clear hover affordance after the pointer leaves the overlay.

        Args:
            event (object): Qt leave event.

        Returns:
            None.
        """
        self._hover_corner = ""
        self.update()
        super().leaveEvent(event)

    def _paint_resize_grip(self, painter: QPainter) -> None:
        """Paint the corner resize triangle grip on the control overlay.

        Args:
            painter (QPainter): Active painter target.

        Returns:
            None.
        """
        _pin, _message, bounds = chrome_geometry(self.width(), self.height())
        inset = max(5, round(bounds.width() * .25))

        painter.setBrush(QColor("#f8fbff"))
        painter.drawPolygon(QPolygonF([
            QPointF(bounds.right() - inset, bounds.bottom() - inset * 2.5),
            QPointF(bounds.right() - inset, bounds.bottom() - inset),
            QPointF(bounds.right() - inset * 2.5, bounds.bottom() - inset),
        ]))

