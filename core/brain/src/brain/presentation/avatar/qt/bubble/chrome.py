# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Qt bubble header, footer, navigation, reply, and zoom chrome."""
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



class QtBubbleChromeMixin:
    """Mixin managing bubble header, footer, navigation, reply, and zoom chrome."""

    def set_theme(self, mode: str) -> None:
        """Apply a complete contrast-safe light or dark bubble palette.

        Args:
            mode (str): Requested theme identifier.

        Returns:
            None.
        """
        normalized = mode if mode in {"light", "dark"} else "light"
        self._theme_mode = normalized
        dark = normalized == "dark"

        text = "#f9edf5" if dark else "#251a28"
        muted = "#dec5d5" if dark else "#513445"
        separator = "rgba(255, 155, 211, 125)" if dark else "rgba(111, 49, 88, 90)"

        palette = self.document_view.palette()
        palette.setColor(QPalette.ColorRole.Text, QColor(text))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(text))
        self.document_view.setPalette(palette)
        self.document_view.setStyleSheet(f"QTextBrowser {{ color: {text}; background: transparent; border: 0; }}")
        self.document_view.document().setDefaultStyleSheet(avatar_document_css(normalized))

        self.source_label.setStyleSheet(f"color: {muted}; background: transparent;")
        self.history_label.setStyleSheet(f"color: {muted}; font: 700 10pt Arial; background: transparent;")
        self.remaining_label.setStyleSheet(
            f"color: {muted}; font: 700 10pt 'Consolas'; background: transparent;",
        )

        self.separator_a_line.setStyleSheet(f"background: {separator}; border: 0;")
        self.separator_b_line.setStyleSheet(f"background: {separator}; border: 0;")
        self.close_button.setStyleSheet(
            f"QToolButton {{ color: {text}; background: transparent; border: 0; font: 700 16px 'Segoe UI Symbol'; }}"
            "QToolButton:hover { color: #ff5b70; }"
        )

        navigation_style = self._navigation_style(dark)
        action_style = self._action_style(dark)

        self.backward_button.setStyleSheet(navigation_style)
        self.forward_button.setStyleSheet(navigation_style)
        self.reply_button.setStyleSheet(action_style)
        self.zoom_out_button.setStyleSheet(action_style)
        self.zoom_in_button.setStyleSheet(action_style)

        self.setProperty("avatarTheme", normalized)
        self._apply_semantic_highlighting()
        self.update()

    def _reply_button(self) -> QToolButton:
        """Create the action that opens the independent reply composer.

        Returns:
            QToolButton: Configured reply button widget.
        """
        button = QToolButton(self.footer)
        button.setText("💭")
        button.setAccessibleName("Responder en Codex")
        button.setToolTip("Responder a este task de Codex")
        button.setFixedSize(26, 24)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            "QToolButton { color: #6f3158; background: transparent; border: 0; font: 700 16px Arial; }"
            "QToolButton:hover { color: #f062b7; } QToolButton:disabled { color: #c6afbd; }"
        )
        button.clicked.connect(self._emit_reply_requested)
        button.setEnabled(False)
        return button

    def _emit_reply_requested(self, _checked: bool = False) -> None:
        """Emit one reply request while suppressing synchronous re-entry.

        Args:
            _checked: Qt's optional check-state argument from the clicked signal.

        Returns:
            None: One guarded request is emitted for the current click.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if getattr(self, "_reply_request_emitting", False):
            return

        self._reply_request_emitting = True

        # Exception safety: execute operation within protected error boundary
        try:
            self.replyRequested.emit()
        finally:
            self._reply_request_emitting = False

    def _zoom_button(self, text: str, accessible_name: str, direction: int) -> QToolButton:
        """Create one message-scale control beside the reply action.

        Args:
            text (str): Button display label ("+" or "-").
            accessible_name (str): Accessible description for screen readers and tooltips.
            direction (int): Zoom direction multiplier (+1 or -1).

        Returns:
            QToolButton: Configured zoom button widget.
        """
        button = QToolButton(self.footer)
        button.setText(text)
        button.setAccessibleName(accessible_name)
        button.setToolTip(accessible_name)
        button.setFixedSize(26, 24)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _checked=False, value=direction: self._adjust_zoom(value))
        return button

    def _rebuild_footer_layout(self, actions_on_right: bool) -> None:
        """Place actions near the avatar and remaining time on the opposite edge.

        Args:
            actions_on_right (bool): Whether actions sit on the right side of the footer.

        Returns:
            None.
        """

        # Loop execution: process until boundary condition is satisfied
        while self.footer_layout.count():
            self.footer_layout.takeAt(0)

        actions = (self.reply_button, self.zoom_out_button, self.zoom_in_button)
        navigation = (self.backward_button, self.history_label, self.forward_button)
        action_width = sum(widget.width() for widget in actions) + self.footer_layout.spacing() * (len(actions) - 1)
        self.remaining_label.setFixedWidth(action_width)

        # Conditional check: evaluate domain preconditions and invariants
        if not actions_on_right:
            # Loop execution: iterate over items
            for widget in actions:
                self.footer_layout.addWidget(widget)
        else:
            self.footer_layout.addWidget(self.remaining_label)

        self.footer_layout.addStretch(1)

        # Loop execution: iterate over items
        for widget in navigation:
            self.footer_layout.addWidget(widget)

        self.footer_layout.addStretch(1)

        # Conditional check: evaluate domain preconditions and invariants
        if actions_on_right:
            # Loop execution: iterate over items
            for widget in reversed(actions):
                self.footer_layout.addWidget(widget)
        else:
            self.footer_layout.addWidget(self.remaining_label)

        self._footer_actions_on_right = actions_on_right

    def set_remaining_seconds(self, remaining_seconds: float) -> None:
        """Render a non-negative presentation countdown as `mm:ss`.

        Args:
            remaining_seconds (float): Fractional duration reported by the voice daemon.

        Returns:
            None.
        """
        total_seconds = max(0, math.ceil(remaining_seconds))
        minutes, seconds = divmod(total_seconds, 60)
        self.remaining_label.setText(f"{minutes:02d}:{seconds:02d}")

    @staticmethod
    def _navigation_style(dark: bool) -> str:
        """Return theme-matched circular history control styling.

        Args:
            dark (bool): Whether dark theme is active.

        Returns:
            str: Stylesheet string for navigation buttons.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if dark:
            return (
                "QToolButton { color: #fff4fb; background: #302832; border: 1px solid #a96b91; "
                "border-radius: 12px; font: 700 16px Arial; }"
                "QToolButton:hover { color: #ffffff; background: #493646; border-color: #ff9bd3; }"
                "QToolButton:disabled { color: #8d7b87; background: #292229; border-color: #685a63; }"
            )

        return (
            "QToolButton { color: #6f3158; background: #fff1f8; border: 1px solid #c87aa9; "
            "border-radius: 12px; font: 700 16px Arial; }"
            "QToolButton:hover { color: #78124e; background: #ffe0f2; border-color: #f062b7; }"
            "QToolButton:disabled { color: #b79aaa; background: #f4e7ef; border-color: #dbcbd5; }"
        )

    @staticmethod
    def _action_style(dark: bool) -> str:
        """Return theme-matched styling for reply and zoom actions.

        Args:
            dark (bool): Whether dark theme is active.

        Returns:
            str: Stylesheet string for action buttons.
        """
        color = "#ffb6df" if dark else "#6f3158"
        hover = "#ffffff" if dark else "#f062b7"
        disabled = "#766571" if dark else "#c6afbd"

        return (
            f"QToolButton {{ color: {color}; background: transparent; border: 0; font: 700 16px Arial; }}"
            f"QToolButton:hover {{ color: {hover}; }} QToolButton:disabled {{ color: {disabled}; }}"
        )

    def _adjust_zoom(self, direction: int) -> None:
        """Scale narrable text and images within bounded accessibility limits.

        Args:
            direction (int): Relative step direction (+1 or -1).

        Returns:
            None.
        """
        next_step = max(-3, min(4, self._zoom_step + direction))

        # Conditional check: evaluate domain preconditions and invariants
        if next_step == self._zoom_step:
            return

        delta = next_step - self._zoom_step
        self._zoom_step = next_step
        self._scale_document_fonts(1.2 ** delta)

        self.zoom_out_button.setEnabled(self._zoom_step > -3)
        self.zoom_in_button.setEnabled(self._zoom_step < 4)

        self._apply_image_dimensions(self._last_image_dimensions)
        self._fit_content_height()

    def _scale_document_fonts(self, factor: float) -> None:
        """Scale every rendered text fragment without splitting inline typography.

        Args:
            factor (float): Multiplicative scaling factor.

        Returns:
            None.
        """
        document = self.document_view.document()
        block = document.begin()

        # Loop execution: process until boundary condition is satisfied
        while block.isValid():
            iterator = block.begin()

            # Loop execution: process until boundary condition is satisfied
            while not iterator.atEnd():
                fragment = iterator.fragment()

                # Conditional check: evaluate domain preconditions and invariants
                if fragment.isValid() and not fragment.charFormat().isImageFormat():
                    char_format = fragment.charFormat()
                    point_size = char_format.font().pointSizeF()
                    char_format.setFontPointSize(max(1.0, point_size * factor))
                    cursor = QTextCursor(document)
                    cursor.setPosition(fragment.position())
                    cursor.setPosition(
                        fragment.position() + fragment.length(),
                        QTextCursor.MoveMode.KeepAnchor,
                    )
                    cursor.mergeCharFormat(char_format)
                iterator += 1

            block = block.next()

    def set_reply_available(self, available: bool) -> None:
        """Enable replies only when displayed message owns a valid target.

        Args:
            available (bool): Whether a reply target is available.

        Returns:
            None.
        """
        self.reply_button.setEnabled(available)

    def _section_separator(self) -> tuple[QWidget, QFrame]:
        """Create a centered line occupying 80% of the current content width.

        Returns:
            tuple[QWidget, QFrame]: Container widget and inner line frame.
        """
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
        separator_layout.addWidget(line, 1)

        return container, line

    def _set_header(self, emotion: str, consumer_path: str, history_index: int, history_total: int) -> None:
        """Update provenance and bounded history navigation state.

        Args:
            emotion (str): Emotion text shown in the header.
            consumer_path (str): File/component path for provenance display.
            history_index (int): Zero-based index of current message.
            history_total (int): Total number of retained messages.

        Returns:
            None.
        """
        self._header_emotion = emotion.strip()
        self._header_consumer_path = consumer_path.strip()

        total = max(1, history_total)
        index = max(0, min(history_index, total - 1))

        self.history_label.setText(f"{total - index}/{total}")
        self.backward_button.setEnabled(index < total - 1)
        self.forward_button.setEnabled(index > 0)
        self.source_label.setToolTip(self._header_consumer_path)
        self._refresh_header_label()

    def _refresh_header_label(self) -> None:
        """Elide repository provenance without losing its full tooltip.

        Returns:
            None.
        """
        prefix = f"{self._header_emotion} " if self._header_emotion else ""
        available = max(80, self.source_label.width())

        path = self.source_label.fontMetrics().elidedText(
            self._header_consumer_path or "Repositorio desconocido",
            Qt.TextElideMode.ElideMiddle,
            max(40, available - self.source_label.fontMetrics().horizontalAdvance(prefix)),
        )
        self.source_label.setText(f"{prefix}{path}")

