# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""PySide6 prototype of the detached Markdown dialogue bubble."""
from __future__ import annotations

import math

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPolygonF,
    QTextCursor,
    QTextFrameFormat,
    QTextTable,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from brain.presentation.avatar.interactivity.markdown_document import AVATAR_DOCUMENT_CSS, avatar_markdown_source


class QtMarkdownBubble(QWidget):
    """Transparent, faithful Qt prototype for rich avatar dialogue."""

    geometryChanged = Signal()
    dismissed = Signal()
    navigateRequested = Signal(int)
    replyRequested = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(320, 92)
        screen = QApplication.primaryScreen()
        screen_height = screen.availableGeometry().height() if screen else 720
        self.setMaximumHeight(max(220, min(420, round(screen_height * .58))))
        self.resize(620, 180)
        self._drag_origin: tuple[QPoint, QPoint] | None = None
        self._resize_origin: tuple[str, QPoint, object] | None = None
        self._tail_target = QPointF(self.width() - 40, self.height() + 40)
        self._manual_size = False
        self._hover_corner = ""
        self._header_emotion = ""
        self._header_consumer_path = ""
        self._placed_above = True
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(80)
        self._hover_timer.timeout.connect(self._sync_resize_hover)
        self._hover_timer.start()

        self.document_view = QTextBrowser(self)
        self.document_view.setFrameShape(QTextBrowser.Shape.NoFrame)
        self.document_view.setOpenExternalLinks(False)
        self.document_view.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        palette = self.document_view.palette()
        palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.transparent)
        palette.setColor(QPalette.ColorRole.Text, QColor("#251a28"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#251a28"))
        self.document_view.setPalette(palette)
        self.document_view.setStyleSheet("QTextBrowser { color: #251a28; background: transparent; border: 0; }")
        self.document_view.document().setDefaultFont(QFont("Arial", 12))
        self.document_view.document().setDefaultStyleSheet(AVATAR_DOCUMENT_CSS)

        self.header = QWidget(self)
        self.header.setFixedHeight(26)
        self.header.setStyleSheet("background: transparent;")
        self.source_label = QLabel(self.header)
        self.source_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.source_label.setStyleSheet("color: #513445; background: transparent;")
        self.source_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 26, 0)
        header_layout.addWidget(self.source_label, 1)

        self.footer = QWidget(self)
        self.footer.setFixedHeight(26)
        self.footer.setStyleSheet("background: transparent;")
        self.backward_button = self._navigation_button("‹", "Mensaje anterior", -1)
        self.history_label = QLabel("1/1", self.footer)
        self.history_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_label.setFixedWidth(40)
        self.history_label.setStyleSheet("color: #765568; font: 700 10pt Arial; background: transparent;")
        self.forward_button = self._navigation_button("›", "Mensaje siguiente", 1)
        self.reply_button = self._reply_button()
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(6)
        footer_layout.addWidget(self.reply_button)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.backward_button)
        footer_layout.addWidget(self.history_label)
        footer_layout.addWidget(self.forward_button)
        footer_layout.addStretch(1)

        self.close_button = QToolButton(self)
        self.close_button.setText("\u00d7")
        self.close_button.setAccessibleName("Cerrar mensaje")
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setFixedSize(24, 24)
        self.close_button.setStyleSheet(
            "QToolButton { color: #111111; background: transparent; border: 0; font: 700 16px 'Segoe UI Symbol'; }"
            "QToolButton:hover { color: #d62839; }"
        )
        self.close_button.clicked.connect(self._dismiss)

        self.separator_a, self.separator_a_line = self._section_separator()
        self.separator_b, self.separator_b_line = self._section_separator()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 34, 24)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.separator_a)
        layout.addWidget(self.document_view)
        layout.addWidget(self.separator_b)
        layout.addWidget(self.footer)
        self._position_close_button()

    def _reply_button(self) -> QToolButton:
        """Create the action that opens the independent reply composer."""
        button = QToolButton(self.footer)
        button.setText("↩")
        button.setAccessibleName("Responder en Codex")
        button.setToolTip("Responder a este task de Codex")
        button.setFixedSize(26, 24)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            "QToolButton { color: #6f3158; background: transparent; border: 0; font: 700 16px Arial; }"
            "QToolButton:hover { color: #f062b7; } QToolButton:disabled { color: #c6afbd; }"
        )
        button.clicked.connect(self.replyRequested.emit)
        button.setEnabled(False)
        return button

    def set_reply_available(self, available: bool) -> None:
        """Enable replies only when the displayed message owns a valid target."""
        self.reply_button.setEnabled(available)

    def _section_separator(self) -> tuple[QWidget, QFrame]:
        """Create a centered line occupying 80% of the current content width."""
        container = QWidget(self)
        container.setFixedHeight(10)
        container.setStyleSheet("background: transparent;")
        line = QFrame(container)
        line.setFixedHeight(1)
        line.setFrameShape(QFrame.Shape.NoFrame)
        line.setStyleSheet("background: rgba(111, 49, 88, 90); border: 0;")
        separator_layout = QHBoxLayout(container)
        separator_layout.setContentsMargins(0, 0, 0, 0)
        separator_layout.setSpacing(0)
        separator_layout.addStretch(1)
        separator_layout.addWidget(line, 8)
        separator_layout.addStretch(1)
        return container, line

    def set_vertical_placement(self, above_avatar: bool) -> None:
        """Keep navigation nearest the avatar by swapping fixed header/footer order."""
        if self._placed_above == above_avatar:
            return
        self._placed_above = above_avatar
        layout = self.layout()
        sections = (self.header, self.separator_a, self.document_view, self.separator_b, self.footer)
        for widget in sections:
            layout.removeWidget(widget)
        if above_avatar:
            ordered = sections
        else:
            ordered = (self.footer, self.separator_a, self.document_view, self.separator_b, self.header)
        for widget in ordered:
            layout.addWidget(widget)
        layout.activate()
        self._position_close_button()

    def _position_close_button(self) -> None:
        """Center the close affordance on the header's actual vertical axis."""
        size = self.close_button.size()
        x = self.header.x() + self.header.width() - size.width()
        y = self.header.y() + (self.header.height() - size.height()) // 2
        self.close_button.move(x, y)

    def _dismiss(self) -> None:
        self.hide()
        self.dismissed.emit()

    def _navigation_button(self, text: str, accessible_name: str, direction: int) -> QToolButton:
        """Create one transparent circular history control."""
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
        if not self.isVisible() or self._resize_origin:
            return
        local = self.mapFromGlobal(QCursor.pos())
        corner = self._resize_corner(QPointF(local)) if self.rect().contains(local) else ""
        if corner != self._hover_corner:
            self._hover_corner = corner
            self.update()

    def set_message(
        self,
        text: str,
        emotion_prefix: str = "",
        consumer_path: str = "",
        history_index: int = 0,
        history_total: int = 1,
    ) -> None:
        """Render one semantic Markdown message without executing external links."""
        self._set_header(emotion_prefix, consumer_path, history_index, history_total)
        self.document_view.setMarkdown(avatar_markdown_source(text))
        self._format_tables()
        self._fit_content_height()

    def _set_header(self, emotion: str, consumer_path: str, history_index: int, history_total: int) -> None:
        """Update provenance and bounded history navigation state."""
        self._header_emotion = emotion.strip()
        self._header_consumer_path = consumer_path.strip()
        total = max(1, history_total)
        index = max(0, min(history_index, total - 1))
        self.history_label.setText(f"{index + 1}/{total}")
        self.backward_button.setEnabled(index < total - 1)
        self.forward_button.setEnabled(index > 0)
        self.source_label.setToolTip(self._header_consumer_path)
        self._refresh_header_label()

    def _refresh_header_label(self) -> None:
        """Elide repository provenance without losing its full tooltip."""
        prefix = f"{self._header_emotion} " if self._header_emotion else ""
        available = max(80, self.source_label.width())
        path = self.source_label.fontMetrics().elidedText(
            self._header_consumer_path or "Repositorio desconocido",
            Qt.TextElideMode.ElideMiddle,
            max(40, available - self.source_label.fontMetrics().horizontalAdvance(prefix)),
        )
        self.source_label.setText(f"{prefix}{path}")

    def _fit_content_height(self) -> None:
        """Fit the real document viewport while reserving a safe footer inset."""
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

    def _format_tables(self) -> None:
        """Apply strong rules and align cells according to readable text length."""
        for frame in self.document_view.document().rootFrame().childFrames():
            if not isinstance(frame, QTextTable):
                continue
            table_format = frame.format()
            table_format.setBorder(2)
            table_format.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
            table_format.setCellPadding(7)
            table_format.setCellSpacing(0)
            frame.setFormat(table_format)
            for row in range(frame.rows()):
                for column in range(frame.columns()):
                    cell = frame.cellAt(row, column)
                    cursor = cell.firstCursorPosition()
                    end = cell.lastCursorPosition().position()
                    probe = QTextCursor(cursor)
                    probe.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                    alignment = (
                        Qt.AlignmentFlag.AlignCenter
                        if len(probe.selectedText().strip()) <= 18
                        else Qt.AlignmentFlag.AlignLeft
                    )
                    while cursor.block().isValid() and cursor.position() <= end:
                        block_format = cursor.blockFormat()
                        block_format.setAlignment(alignment)
                        cursor.setBlockFormat(block_format)
                        if not cursor.movePosition(QTextCursor.MoveOperation.NextBlock):
                            break

    def set_tail_target(self, global_target: QPoint) -> None:
        """Point the tail toward one global avatar coordinate without moving the bubble."""
        self._tail_target = QPointF(self.mapFromGlobal(global_target))
        self.update()

    def set_pinned(self, pinned: bool) -> None:
        """Keep window priority synchronized with its owning avatar."""
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, pinned)
        if was_visible:
            self.show()
            self.raise_()

    def _resize_corner(self, position: QPointF) -> str:
        tail_space = 22
        corners = {"nw": QPointF(tail_space, tail_space), "ne": QPointF(self.width() - tail_space, tail_space),
                   "sw": QPointF(tail_space, self.height() - tail_space), "se": QPointF(self.width() - tail_space, self.height() - tail_space)}
        corner, distance = min(((name, (position - point).manhattanLength()) for name, point in corners.items()), key=lambda item: item[1])
        return corner if distance <= 22 else ""

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        corner = self._resize_corner(event.position())
        if corner:
            self._resize_origin = (corner, event.globalPosition().toPoint(), self.geometry())
        else:
            self._drag_origin = (event.globalPosition().toPoint(), self.pos())
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._resize_origin:
            corner, pointer, geometry = self._resize_origin
            delta = event.globalPosition().toPoint() - pointer
            left, top, right, bottom = geometry.left(), geometry.top(), geometry.right(), geometry.bottom()
            if "w" in corner:
                left = min(right - self.minimumWidth(), left + delta.x())
            else:
                right = max(left + self.minimumWidth(), right + delta.x())
            if "n" in corner:
                top = max(bottom - self.maximumHeight(), min(bottom - self.minimumHeight(), top + delta.y()))
            else:
                bottom = min(top + self.maximumHeight(), max(top + self.minimumHeight(), bottom + delta.y()))
            self.setGeometry(left, top, right - left + 1, bottom - top + 1)
            self._manual_size = True
        elif self._drag_origin:
            pointer, origin = self._drag_origin
            self.move(origin + event.globalPosition().toPoint() - pointer)
        else:
            corner = self._resize_corner(event.position())
            self._hover_corner = corner
            cursor = Qt.CursorShape.SizeFDiagCursor if corner in {"nw", "se"} else Qt.CursorShape.SizeBDiagCursor if corner else Qt.CursorShape.ArrowCursor
            self.setCursor(cursor)
            self.update()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._drag_origin = None
        self._resize_origin = None
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._hover_corner = ""
        self.update()
        super().leaveEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if self.layout():
            self.layout().activate()
        self._position_close_button()
        self._refresh_header_label()
        self.geometryChanged.emit()

    def moveEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().moveEvent(event)
        self.geometryChanged.emit()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        """Paint the current pink rounded bubble and lower-right tail."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#f062b7"), 3))
        painter.setBrush(QColor("#fff8fd"))
        tail_space = 22
        body = QRectF(tail_space, tail_space, self.width() - tail_space * 2, self.height() - tail_space * 2)
        body_path = QPainterPath()
        body_path.addRoundedRect(body, 16, 16)
        delta_x = self._tail_target.x() - self.width() / 2
        delta_y = self._tail_target.y() - self.height() / 2
        normalized_x = delta_x / max(1, self.width() / 2)
        normalized_y = delta_y / max(1, self.height() / 2)
        if abs(normalized_x) > abs(normalized_y):
            side = "right" if delta_x >= 0 else "left"
        else:
            side = "bottom" if delta_y >= 0 else "top"
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
        if self._hover_corner:
            corners = {"nw": body.topLeft(), "ne": body.topRight(), "sw": body.bottomLeft(), "se": body.bottomRight()}
            painter.setPen(QPen(QColor("#ffffff"), 1))
            painter.setBrush(QColor("#f062b7"))
            painter.drawEllipse(corners[self._hover_corner], 5, 5)
        painter.end()
