# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Qt bubble sizing, tail, drag, resize, and paint behavior."""
from __future__ import annotations

import math
import os
import re
from pathlib import Path
from urllib.request import Request, urlopen

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QColor, QCursor, QFont, QImage, QPainter, QPainterPath, QPalette, QPen,
    QPolygonF, QTextCharFormat, QTextCursor, QTextDocument, QTextFrameFormat,
    QTextLength, QTextTable,
)
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QSizePolicy, QTextBrowser,
    QToolButton, QVBoxLayout, QWidget,
)

from brain.presentation.avatar.interactivity.markdown_document import (
    AVATAR_BASE_FONT_POINTS, AVATAR_DOCUMENT_CSS, avatar_document_css,
    avatar_markdown_source,
)


UNBOUNDED_WIDGET_HEIGHT = 16_777_215


class QtBubbleGeometryMixin:
    """Mixin managing bubble size bounds, layout placement, tail geometry, and mouse drag/resize."""

    def set_vertical_height_limit(
        self,
        vertically_detached: bool,
        available_height: int | None = None,
        fit_content: bool = True,
    ) -> None:
        """Replace the standard cap with the usable vertical lane height.

        Args:
            vertically_detached (bool): Whether the bubble occupies a lane above or below the avatar.
            available_height (int | None): Maximum lane height before reaching the avatar or screen edge.
            fit_content (bool): Whether changing the ceiling immediately refits rendered content.

        Returns:
            None.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if vertically_detached:
            maximum_height = max(self.minimumHeight(), available_height or UNBOUNDED_WIDGET_HEIGHT)
        else:
            maximum_height = self._standard_maximum_height

        self.setMaximumHeight(maximum_height)

        # Conditional check: evaluate domain preconditions and invariants
        if fit_content:
            self._fit_content_height()

    def reset_geometry(self) -> None:
        """Restore automatic bubble sizing and clear drag/resize state.

        Returns:
            None: The bubble returns to its default uncustomized dimensions.
        """
        self._drag_origin = None
        self._resize_origin = None
        self._hover_corner = ""
        self._manual_size = False
        self.setMaximumHeight(self._standard_maximum_height)
        default_size = QSize(getattr(self, "_default_size", QSize(620, 180)))
        self.resize(default_size)

    def set_vertical_placement(self, above_avatar: bool) -> None:
        """Keep navigation nearest the avatar by swapping header/footer order.

        Args:
            above_avatar (bool): Whether the bubble is above its avatar.

        Returns:
            None.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if self._placed_above == above_avatar:
            return

        self._placed_above = above_avatar
        layout = self.layout()
        sections = (self.header, self.separator_a, self.document_view, self.separator_b, self.footer)

        # Loop execution: iterate over items
        for widget in sections:
            layout.removeWidget(widget)

        # Conditional check: evaluate domain preconditions and invariants
        if above_avatar:
            ordered = sections
        else:
            ordered = (self.footer, self.separator_a, self.document_view, self.separator_b, self.header)

        # Loop execution: iterate over items
        for widget in ordered:
            layout.addWidget(widget)

        layout.activate()
        self._position_close_button()

    def _position_close_button(self) -> None:
        """Center the close affordance on the header's actual vertical axis.

        Returns:
            None.
        """
        size = self.close_button.size()
        x = self.header.x() + self.header.width() - size.width()
        y = self.header.y() + (self.header.height() - size.height()) // 2
        self.close_button.move(x, y)

    def _dismiss(self) -> None:
        """Hide bubble and emit dismissed signal.

        Returns:
            None.
        """
        self.hide()
        self.dismissed.emit()

    def _navigation_button(self, text: str, accessible_name: str, direction: int) -> QToolButton:
        """Create one transparent circular history control.

        Args:
            text (str): Button text symbol ("‹" or "›").
            accessible_name (str): Accessible description for screen readers and tooltips.
            direction (int): Relative step direction (-1 or +1).

        Returns:
            QToolButton: Configured navigation button widget.
        """
        button = QToolButton(self.footer)
        button.setText(text)
        button.setAccessibleName(accessible_name)
        button.setFixedSize(24, 24)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            "QToolButton { color: #6f3158; background: rgba(255,255,255,80); border: 1px solid #c87aa9; "
            "border-radius: 12px; font: 700 16px Arial; }"
            "QToolButton:hover { background: rgba(240,98,183,35); border-color: #f062b7; }"
            "QToolButton:disabled { color: #c6afbd; border-color: #dbcbd5; }"
        )
        button.clicked.connect(lambda _checked=False, value=direction: self.navigateRequested.emit(value))
        return button

    def _sync_resize_hover(self) -> None:
        """Synchronize resize corner hover state under pointer.

        Returns:
            None.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if not self.isVisible() or self._resize_origin:
            return

        local = self.mapFromGlobal(QCursor.pos())
        corner = self._resize_corner(QPointF(local)) if self.rect().contains(local) else ""

        # Conditional check: evaluate domain preconditions and invariants
        if corner != self._hover_corner:
            self._hover_corner = corner
            self.update()

    def _fit_content_height(self) -> None:
        """Fit the real document viewport while reserving a safe footer inset.

        Returns:
            None.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if self.layout():
            self.layout().activate()

        document = self.document_view.document()
        document.setTextWidth(max(220, self.document_view.width()))

        content_height = math.ceil(document.documentLayout().documentSize().height())

        layout_margins = self.layout().contentsMargins() if self.layout() else None
        vertical_chrome = layout_margins.top() + layout_margins.bottom() if layout_margins else 74

        fixed_widgets = (self.header, self.footer, self.separator_a, self.separator_b)
        fixed_chrome = sum(widget.height() for widget in fixed_widgets)
        fixed_chrome += self.layout().spacing() * max(0, self.layout().count() - 1)

        target_height = content_height + vertical_chrome + fixed_chrome + 16
        self.resize(self.width(), max(self.minimumHeight(), min(self.maximumHeight(), target_height)))

    def set_tail_target(self, global_target: QPoint) -> None:
        """Point tail toward avatar coordinates without moving the bubble.

        Args:
            global_target (QPoint): Avatar target in global screen coordinates.

        Returns:
            None.
        """
        self._tail_target = QPointF(self.mapFromGlobal(global_target))
        actions_on_right = self._tail_target.x() >= self.width() / 2
        self._sync_tail_layout_margins()

        # Conditional check: evaluate domain preconditions and invariants
        if actions_on_right != self._footer_actions_on_right:
            self._rebuild_footer_layout(actions_on_right)
        self.update()

    def _tail_side(self) -> str:
        """Resolve the side currently facing the avatar tail target.

        Returns:
            str: One of top, bottom, left, or right.
        """
        delta_x = self._tail_target.x() - self.width() / 2
        delta_y = self._tail_target.y() - self.height() / 2
        normalized_x = delta_x / max(1, self.width() / 2)
        normalized_y = delta_y / max(1, self.height() / 2)

        # Conditional check: evaluate domain preconditions and invariants
        if abs(normalized_x) > abs(normalized_y):
            return "right" if delta_x >= 0 else "left"

        return "bottom" if delta_y >= 0 else "top"

    def _sync_tail_layout_margins(self) -> None:
        """Reserve internal layout space only beside the active tail.

        Returns:
            None: Inactive sides use compact rounded-body padding.
        """
        layout = self.layout()

        # Conditional check: evaluate domain preconditions and invariants
        if layout is None:
            return

        outer_inset = 6
        content_inset = 10
        tail_space = 22
        side = self._tail_side()

        # Conditional check: evaluate domain preconditions and invariants
        if side in {"top", "bottom"}:
            left = content_inset + outer_inset
            right = content_inset + outer_inset
            vertical_inset = 17
            top = content_inset + vertical_inset
            bottom = content_inset + vertical_inset
        else:
            horizontal_inset = 17
            left = content_inset + horizontal_inset
            right = content_inset + horizontal_inset
            top = content_inset + outer_inset
            bottom = content_inset + outer_inset
        layout.setContentsMargins(left, top, right, bottom)
        layout.activate()

    def set_pinned(self, pinned: bool) -> None:
        """Keep window priority synchronized with its owning avatar.

        Args:
            pinned (bool): Whether the bubble should remain topmost.

        Returns:
            None.
        """
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, pinned)

        # Conditional check: evaluate domain preconditions and invariants
        if was_visible:
            self.show()
            self.raise_()

    def _resize_corner(self, position: QPointF) -> str:
        """Resolve closest resize corner identifier for a local point.

        Args:
            position (QPointF): Local mouse position within the bubble widget.

        Returns:
            str: Corner code ("nw", "ne", "sw", "se") or empty string if not over a corner.
        """
        body = self._bubble_body_rect()
        corners = {
            "nw": body.topLeft(),
            "ne": body.topRight(),
            "sw": body.bottomLeft(),
            "se": body.bottomRight(),
        }
        corner, distance = min(
            ((name, (position - point).manhattanLength()) for name, point in corners.items()),
            key=lambda item: item[1],
        )
        return corner if distance <= 22 else ""

    def _bubble_body_rect(self) -> QRectF:
        """Return the painted body rectangle for the current tail axis.

        Returns:
            QRectF: Body bounds shared by painting and resize-handle detection.
        """
        outer_inset = 6
        balanced_tail_inset = 17
        body = QRectF(
            outer_inset,
            outer_inset,
            self.width() - outer_inset * 2,
            self.height() - outer_inset * 2,
        )

        # Conditional check: evaluate domain preconditions and invariants
        if self._tail_side() in {"top", "bottom"}:
            body.setTop(balanced_tail_inset)
            body.setBottom(self.height() - balanced_tail_inset)
        else:
            body.setLeft(balanced_tail_inset)
            body.setRight(self.width() - balanced_tail_inset)

        return body

    def mousePressEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Begin a bubble drag or resize interaction.

        Args:
            event (object): Qt mouse-press event.

        Returns:
            None.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)

        corner = self._resize_corner(event.position())

        # Conditional check: evaluate domain preconditions and invariants
        if corner:
            self._refresh_resize_height_limit()
            self._resize_origin = (corner, event.globalPosition().toPoint(), self.geometry())
        else:
            self._drag_origin = (event.globalPosition().toPoint(), self.pos())

        event.accept()

    def _refresh_resize_height_limit(self) -> None:
        """Recalculate the vertical resize ceiling from the live anchor edge.

        Returns:
            None: The next corner resize may use the complete viewport lane.
        """
        screen = QApplication.screenAt(self.frameGeometry().center())

        # Conditional check: evaluate domain preconditions and invariants
        if screen is None:
            screen = QApplication.primaryScreen()

        # Conditional check: evaluate domain preconditions and invariants
        if screen is None:
            return

        viewport = screen.availableGeometry()
        geometry = self.frameGeometry()
        side = self._tail_side()

        # Conditional check: evaluate domain preconditions and invariants
        if side == "bottom":
            maximum_height = geometry.bottom() - viewport.top() + 1

        # Conditional check: evaluate domain preconditions and invariants
        elif side == "top":
            maximum_height = viewport.bottom() - geometry.top() + 1
        else:
            maximum_height = viewport.height()

        self.setMaximumHeight(max(self.minimumHeight(), maximum_height))

    def mouseMoveEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Move or resize the bubble from current pointer interaction.

        Args:
            event (object): Qt mouse-move event.

        Returns:
            None.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if self._resize_origin:
            corner, pointer, geometry = self._resize_origin
            delta = event.globalPosition().toPoint() - pointer
            left, top, right, bottom = geometry.left(), geometry.top(), geometry.right(), geometry.bottom()

            # Conditional check: evaluate domain preconditions and invariants
            if "w" in corner:
                left = min(right - self.minimumWidth(), left + delta.x())
            else:
                right = max(left + self.minimumWidth(), right + delta.x())

            # Conditional check: evaluate domain preconditions and invariants
            if "n" in corner:
                top = max(bottom - self.maximumHeight(), min(bottom - self.minimumHeight(), top + delta.y()))
            else:
                bottom = min(top + self.maximumHeight(), max(top + self.minimumHeight(), bottom + delta.y()))

            self.setGeometry(left, top, right - left + 1, bottom - top + 1)
            self._manual_size = True

        # Conditional check: evaluate domain preconditions and invariants
        elif self._drag_origin:
            pointer, origin = self._drag_origin
            self.move(origin + event.globalPosition().toPoint() - pointer)
        else:
            corner = self._resize_corner(event.position())
            self._hover_corner = corner
            cursor = (
                Qt.CursorShape.SizeFDiagCursor if corner in {"nw", "se"}
                else Qt.CursorShape.SizeBDiagCursor if corner
                else Qt.CursorShape.ArrowCursor
            )
            self.setCursor(cursor)
            self.update()

        event.accept()

    def mouseReleaseEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """End bubble drag or resize interaction.

        Args:
            event (object): Qt mouse-release event.

        Returns:
            None.
        """
        was_manipulating = self._drag_origin is not None or self._resize_origin is not None
        self._drag_origin = None
        self._resize_origin = None

        # Conditional check: evaluate domain preconditions and invariants
        if was_manipulating:
            self.manuallyMoved.emit()

        super().mouseReleaseEvent(event)

    def leaveEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Clear resize-hover affordance after pointer leave.

        Args:
            event (object): Qt leave event.

        Returns:
            None.
        """
        self._hover_corner = ""
        self.update()
        super().leaveEvent(event)

    def resizeEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Refresh header and document geometry after a bubble resize.

        Args:
            event (object): Qt resize event.

        Returns:
            None.
        """
        super().resizeEvent(event)

        # Conditional check: evaluate domain preconditions and invariants
        if self.layout():
            self.layout().activate()

        self._position_close_button()
        self._refresh_header_label()

        # Conditional check: evaluate domain preconditions and invariants
        if self._last_image_dimensions or "<img" in self.document_view.document().toHtml():
            self._apply_image_dimensions(self._last_image_dimensions)

        self.geometryChanged.emit()

    def moveEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Publish geometry changes after a bubble move.

        Args:
            event (object): Qt move event.

        Returns:
            None.
        """
        super().moveEvent(event)
        self.geometryChanged.emit()

    def paintEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Paint current rounded bubble and directional tail.

        Args:
            event (object): Qt paint event.

        Returns:
            None.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        dark = self._theme_mode == "dark"

        painter.setPen(QPen(QColor("#ff74c4" if dark else "#f062b7"), 3))
        painter.setBrush(QColor("#1f1722" if dark else "#fff8fd"))

        delta_x = self._tail_target.x() - self.width() / 2
        delta_y = self._tail_target.y() - self.height() / 2
        side = self._tail_side()

        tail_space = 22
        body = self._bubble_body_rect()

        body_path = QPainterPath()
        body_path.addRoundedRect(body, 16, 16)

        # Conditional check: evaluate domain preconditions and invariants
        if side in {"top", "bottom"}:
            target = max(body.left() + 20, min(body.right() - 20, self._tail_target.x()))
            edge = body.top() + 4 if side == "top" else body.bottom() - 4
            tip = QPointF(target, 5 if side == "top" else self.height() - 5)
            tail = QPolygonF([QPointF(target - 17, edge), QPointF(target + 17, edge), tip])
        else:
            target = max(body.top() + 20, min(body.bottom() - 20, self._tail_target.y()))
            edge = body.left() + 4 if side == "left" else body.right() - 4
            tip = QPointF(5 if side == "left" else self.width() - 5, target)
            tail = QPolygonF([QPointF(edge, target - 17), QPointF(edge, target + 17), tip])

        tail_path = QPainterPath()
        tail_path.addPolygon(tail)
        tail_path.closeSubpath()
        painter.drawPath(body_path.united(tail_path))

        # Conditional check: evaluate domain preconditions and invariants
        if self._hover_corner:
            corners = {
                "nw": body.topLeft(),
                "ne": body.topRight(),
                "sw": body.bottomLeft(),
                "se": body.bottomRight(),
            }
            painter.setPen(QPen(QColor("#1f1722" if dark else "#ffffff"), 1))
            painter.setBrush(QColor("#f062b7"))
            painter.drawEllipse(corners[self._hover_corner], 5, 5)

        painter.end()

