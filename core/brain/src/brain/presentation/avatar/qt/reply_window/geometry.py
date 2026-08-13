"""Geometry and pointer interactions for the Qt reply composer."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QMouseEvent, QMoveEvent, QResizeEvent
from PySide6.QtWidgets import QApplication


class QtReplyWindowGeometryMixin:
    """Keep reply-composer geometry safe and retain user pointer changes.

    Attributes:
        _SCREEN_MARGIN: Safe distance from the available screen edge.
    """

    _SCREEN_MARGIN: int = 18

    def _calculate_chrome_minimum_size(self) -> QSize:
        """Calculate the minimum size required by the composer chrome.

        Args:

        Returns:
            QSize: Minimum usable composer dimensions.
        """
        layout = self.layout()

        # Conditional check: evaluate domain preconditions and invariants
        if layout is None:
            return QSize(320, 92)

        layout.activate()
        minimum = layout.minimumSize()

        return QSize(max(320, minimum.width()), max(92, minimum.height()))

    @classmethod
    def _safe_screen_rect(
        cls,
        screen: QRect,
        *,
        horizontal_margin: int | None = None,
    ) -> QRect:
        """Return the available screen area after the composer margin.

        Args:
            screen: Available geometry of the active screen.
            horizontal_margin: Optional horizontal margin override.

        Returns:
            QRect: Non-empty screen area reserved for the composer.
        """
        requested_horizontal_margin = (
            cls._SCREEN_MARGIN
            if horizontal_margin is None
            else horizontal_margin
        )
        horizontal_padding = min(
            max(0, requested_horizontal_margin),
            max(0, (screen.width() - 1) // 2),
        )
        vertical_margin = min(cls._SCREEN_MARGIN, max(0, (screen.height() - 1) // 2))
        left = screen.left() + horizontal_padding
        top = screen.top() + vertical_margin
        right = max(left, screen.right() - horizontal_padding)
        bottom = max(top, screen.bottom() - vertical_margin)

        return QRect(left, top, max(1, right - left + 1), max(1, bottom - top + 1))

    def _available_screen_geometry(self, geometry: QRect | None = None) -> QRect | None:
        """Resolve the available geometry for the screen containing a point.

        Args:
            geometry: Optional geometry whose center selects the active screen.

        Returns:
            QRect | None: Available screen rectangle, or None without a Qt screen.
        """
        application = QApplication.instance()

        # Conditional check: evaluate domain preconditions and invariants
        if application is None:
            return None

        reference = geometry.center() if geometry is not None else self.frameGeometry().center()
        screen = application.screenAt(reference) or application.primaryScreen()

        return screen.availableGeometry() if screen is not None else None

    def safe_minimum_size(
        self,
        screen: QRect | None = None,
        *,
        horizontal_margin: int | None = None,
    ) -> QSize:
        """Return a chrome-safe minimum clamped to the active screen.

        Args:
            screen: Optional available screen rectangle used for clamping.
            horizontal_margin: Optional horizontal margin override.

        Returns:
            QSize: Minimum composer size that keeps its controls usable.
        """
        available = screen or self._available_screen_geometry()

        # Conditional check: evaluate domain preconditions and invariants
        if available is None:
            return QSize(self._chrome_minimum_size)

        safe_area = self._safe_screen_rect(
            available,
            horizontal_margin=horizontal_margin,
        )

        return QSize(
            min(self._chrome_minimum_size.width(), safe_area.width()),
            min(self._chrome_minimum_size.height(), safe_area.height()),
        )

    def _bounded_geometry(
        self,
        geometry: QRect,
        screen: QRect | None = None,
        *,
        horizontal_margin: int | None = None,
    ) -> QRect:
        """Clamp a requested rectangle to one screen's safe area.

        Args:
            geometry: Requested top-left point and dimensions.
            screen: Optional available screen rectangle for the clamp.
            horizontal_margin: Optional horizontal margin override.

        Returns:
            QRect: Screen-safe rectangle preserving requested dimensions when possible.
        """
        available = screen or self._available_screen_geometry(geometry)

        # Conditional check: evaluate domain preconditions and invariants
        if available is None:
            return QRect(geometry)

        safe_area = self._safe_screen_rect(
            available,
            horizontal_margin=horizontal_margin,
        )
        minimum = self.safe_minimum_size(
            available,
            horizontal_margin=horizontal_margin,
        )
        width = min(safe_area.width(), max(minimum.width(), geometry.width(), 1))
        height = min(safe_area.height(), max(minimum.height(), geometry.height(), 1))
        maximum_left = safe_area.right() - width + 1
        maximum_top = safe_area.bottom() - height + 1
        left = max(safe_area.left(), min(geometry.left(), maximum_left))
        top = max(safe_area.top(), min(geometry.top(), maximum_top))

        return QRect(left, top, width, height)

    def _apply_geometry(
        self,
        geometry: QRect,
        *,
        horizontal_margin: int | None = None,
    ) -> QRect:
        """Apply one internally managed, screen-safe composer rectangle.

        Args:
            geometry: Requested composer rectangle.
            horizontal_margin: Optional horizontal margin override.

        Returns:
            QRect: Actual geometry after Qt and screen constraints are applied.
        """
        available = self._available_screen_geometry(geometry)

        # Guard clause: verify required active entity presence
        if available is not None:
            self.setMinimumSize(
                self.safe_minimum_size(
                    available,
                    horizontal_margin=horizontal_margin,
                )
            )

        else:
            self.setMinimumSize(self._chrome_minimum_size)

        bounded = self._bounded_geometry(
            geometry,
            available,
            horizontal_margin=horizontal_margin,
        )
        self._applying_geometry = True

        # Exception safety: execute operation within protected error boundary
        try:
            self.setGeometry(bounded)

        finally:
            self._applying_geometry = False

        return QRect(self.geometry())

    def apply_automatic_geometry(
        self,
        geometry: QRect,
        *,
        preserve_horizontal_anchor: bool = False,
    ) -> QRect:
        """Apply automatic geometry without replacing a user-selected rectangle.

        Args:
            geometry: Automatic rectangle selected by the avatar owner.
            preserve_horizontal_anchor: Whether the rectangle may touch the
                available screen's horizontal edges to match the bubble frame.

        Returns:
            QRect: Current composer geometry after the bounded application.
        """
        if self._manual_geometry is not None:
            return QRect(self.geometry())

        horizontal_margin = 0 if preserve_horizontal_anchor else None

        return self._apply_geometry(
            geometry,
            horizontal_margin=horizontal_margin,
        )

    def reset_geometry(self, geometry: QRect | None = None) -> None:
        """Clear retained geometry and apply the next automatic rectangle.

        Args:
            geometry: Optional automatic rectangle selected by the avatar owner.

        Returns:
            None: Manual position and size are forgotten without changing reply state.
        """
        self._manual_geometry = None
        self._drag_pointer = None
        self._drag_origin = None
        self._resize_origin = None
        self._hover_corner = ""
        self.unsetCursor()

        # Conditional check: evaluate domain preconditions and invariants
        if geometry is None:
            available = self._available_screen_geometry()
            default_size = QSize(570, 270)

            # Conditional check: evaluate domain preconditions and invariants
            if available is None:
                geometry = QRect(self.pos(), default_size)

            else:
                safe_area = self._safe_screen_rect(available)
                available_width = safe_area.width()
                available_height = safe_area.height()
                horizontal_space = available_width - default_size.width()
                vertical_space = available_height - default_size.height()
                horizontal_offset = max(0, horizontal_space // 2)
                vertical_offset = max(0, vertical_space // 2)
                left = safe_area.left() + horizontal_offset
                top = safe_area.top() + vertical_offset
                geometry = QRect(left, top, default_size.width(), default_size.height())

        self._apply_geometry(geometry)

    def _remember_manual_geometry(self) -> None:
        """Record the current rectangle after a user geometry change.

        Args:

        Returns:
            None: The current rectangle becomes the retained manual rectangle.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if self._applying_geometry:
            return

        self._manual_geometry = QRect(self.geometry())

    def _resize_corner(self, position: QPointF) -> str:
        """Resolve the corner handle under a local pointer position.

        Args:
            position: Local pointer coordinates inside the composer.

        Returns:
            str: One of nw, ne, sw, se, or an empty string.
        """
        handle_size = 12
        left = position.x() <= handle_size
        right = position.x() >= self.width() - handle_size
        top = position.y() <= handle_size
        bottom = position.y() >= self.height() - handle_size

        # Conditional check: evaluate domain preconditions and invariants
        if left and top:

            return "nw"

        # Conditional check: evaluate domain preconditions and invariants
        if right and top:
            return "ne"

        # Conditional check: evaluate domain preconditions and invariants
        if left and bottom:
            return "sw"

        # Conditional check: evaluate domain preconditions and invariants
        if right and bottom:
            return "se"

        return ""

    @staticmethod
    def _resize_cursor(corner: str) -> Qt.CursorShape:
        """Return the native cursor shape for one corner handle.

        Args:
            corner: Corner identifier.

        Returns:
            Qt.CursorShape: Diagonal resize cursor or the default arrow.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if corner in {"nw", "se"}:
            return Qt.CursorShape.SizeFDiagCursor

        # Conditional check: evaluate domain preconditions and invariants
        if corner in {"ne", "sw"}:
            return Qt.CursorShape.SizeBDiagCursor

        return Qt.CursorShape.ArrowCursor

    def _resized_geometry(self, corner: str, delta: QPoint, origin: QRect) -> QRect:
        """Calculate one bounded rectangle during a corner resize.

        Args:
            corner: Active corner identifier.
            delta: Global pointer displacement from resize start.
            origin: Geometry captured at resize start.

        Returns:
            QRect: Rectangle respecting minimum size and screen bounds.
        """
        available = self._available_screen_geometry(origin)
        safe_area = self._safe_screen_rect(available) if available is not None else None
        minimum = self.safe_minimum_size(available)
        left = origin.left()
        top = origin.top()
        right = origin.right()
        bottom = origin.bottom()

        # Conditional check: evaluate domain preconditions and invariants
        if "w" in corner:
            requested_left = origin.left() + delta.x()
            minimum_left = right - minimum.width() + 1
            left = min(minimum_left, requested_left)

            # Guard clause: verify required active entity presence
            if safe_area is not None:
                left = max(safe_area.left(), left)

        else:
            requested_right = origin.right() + delta.x()
            minimum_right = left + minimum.width() - 1
            right = max(minimum_right, requested_right)

            # Guard clause: verify required active entity presence
            if safe_area is not None:
                right = min(safe_area.right(), right)

        # Conditional check: evaluate domain preconditions and invariants
        if "n" in corner:
            requested_top = origin.top() + delta.y()
            minimum_top = bottom - minimum.height() + 1
            top = min(minimum_top, requested_top)

            # Guard clause: verify required active entity presence
            if safe_area is not None:
                top = max(safe_area.top(), top)

        else:
            requested_bottom = origin.bottom() + delta.y()
            minimum_bottom = top + minimum.height() - 1
            bottom = max(minimum_bottom, requested_bottom)

            # Guard clause: verify required active entity presence
            if safe_area is not None:
                bottom = min(safe_area.bottom(), bottom)

        candidate = QRect(left, top, right - left + 1, bottom - top + 1)

        return self._bounded_geometry(candidate, available)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Begin a corner resize or header drag interaction.

        Args:
            event: Qt mouse-press event.

        Returns:
            None: The event is accepted when it starts a header drag or resize.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)

            return

        corner = self._resize_corner(event.position())

        # Conditional check: evaluate domain preconditions and invariants
        if corner:
            self._resize_origin = (
                corner,
                event.globalPosition().toPoint(),
                QRect(self.geometry()),
            )
            self._hover_corner = corner
            self.setCursor(self._resize_cursor(corner))
            event.accept()

            return

        # Conditional check: evaluate domain preconditions and invariants
        if event.position().y() > 58:
            super().mousePressEvent(event)

            return

        self._drag_pointer = event.globalPosition().toPoint()
        self._drag_origin = self.pos()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Resize or move the detached composer from current pointer input.

        Args:
            event: Qt mouse-move event.

        Returns:
            None: The window moves while a header drag is active.
        """
        global_position = event.globalPosition().toPoint()

        # Guard clause: verify required active entity presence
        if self._resize_origin is not None:

            corner, pointer, origin = self._resize_origin
            delta = global_position - pointer
            self._apply_geometry(self._resized_geometry(corner, delta, origin))
            event.accept()

            return

        # Guard clause: verify required active entity presence
        if self._drag_pointer is not None and self._drag_origin is not None:

            pointer_offset = global_position - self._drag_pointer
            next_geometry = QRect(self._drag_origin + pointer_offset, self.size())
            self._apply_geometry(next_geometry)
            event.accept()

            return

        corner = self._resize_corner(event.position())
        self._hover_corner = corner
        self.setCursor(self._resize_cursor(corner))
        self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Clear composer drag or resize state.

        Args:
            event: Qt mouse-release event.

        Returns:
            None: Drag state is cleared after the release event.
        """
        was_manipulating = (
            self._drag_pointer is not None or self._resize_origin is not None
        )
        self._drag_pointer = None
        self._drag_origin = None
        self._resize_origin = None

        # Conditional check: evaluate domain preconditions and invariants
        if was_manipulating:

            self._remember_manual_geometry()
            event.accept()

        super().mouseReleaseEvent(event)

    def leaveEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Clear corner hover state after the pointer leaves the composer.

        Args:
            event: Qt leave event.

        Returns:
            None: Corner affordances and cursors return to their defaults.
        """
        self._hover_corner = ""
        self.unsetCursor()
        self.update()
        super().leaveEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt API
        """Remember user-driven composer size changes.

        Args:
            event: Qt resize event.

        Returns:
            None: Automatic geometry changes remain uncustomized.
        """
        super().resizeEvent(event)
        self._remember_manual_geometry()

    def moveEvent(self, event: QMoveEvent) -> None:  # noqa: N802 - Qt API
        """Remember user-driven composer position changes.

        Args:
            event: Qt move event.

        Returns:
            None: Automatic geometry changes remain uncustomized.
        """
        super().moveEvent(event)
        self._remember_manual_geometry()
