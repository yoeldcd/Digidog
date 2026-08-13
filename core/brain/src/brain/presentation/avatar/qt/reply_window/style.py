"""Theme styling and surface painting for the Qt reply composer."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QPushButton, QSizePolicy


class QtReplyWindowStyleMixin:
    """Manage composer theme styles, action button chrome, and painting."""

    def set_theme(self, mode: str) -> None:
        """Apply active light or dark palette to the reply composer.

        Args:
            mode: Requested theme identifier.

        Returns:
            None: Widget colors and the active theme property are updated.
        """
        normalized = mode if mode in {"light", "dark"} else "light"
        self._theme_mode = normalized

        dark = normalized == "dark"
        text = "#fff4fb" if dark else "#251a28"
        muted = "#dec5d5" if dark else "#6f3158"
        editor_surface = "#2b222d" if dark else "#ffffff"
        editor_border = "#a96b91" if dark else "#dfbfd2"

        self.title_label.setStyleSheet(f"color: {text}; background: transparent;")
        self.target_label.setStyleSheet(f"color: {muted}; background: transparent;")
        self.status_label.setStyleSheet(
            f"color: {muted}; background: transparent; padding: 0 3px;"
        )
        self.close_button.setStyleSheet(
            f"QToolButton {{ color: {text}; background: transparent; border: 0; font: 700 18px Arial; }}"
            "QToolButton:hover { color: #ff5b70; background: rgba(214,40,57,24); border-radius: 14px; }"
        )
        self.editor.setStyleSheet(
            f"QTextEdit {{ color: {text}; background: {editor_surface}; border: 1px solid {editor_border}; "
            "border-radius: 12px; padding: 10px; selection-background-color: #f062b7; }"
            "QTextEdit:focus { border: 2px solid #f062b7; padding: 9px; }"
        )

        # Loop execution: iterate over items
        for button in self._action_buttons:
            self._style_action_button(
                button,
                bool(button.property("primaryAction")),
                dark,
            )
        self.setProperty("avatarTheme", normalized)
        self.update()

    def _action_button(self, text: str, primary: bool) -> QPushButton:
        """Create and style one reply action button.

        Args:
            text: Visible button label.
            primary: Whether to use the primary action palette.

        Returns:
            QPushButton: Configured action button.
        """
        button = QPushButton(text, self)
        button.setProperty("primaryAction", primary)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(30)
        button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._style_action_button(button, primary, self._theme_mode == "dark")

        return button

    @staticmethod
    def _style_action_button(button: QPushButton, primary: bool, dark: bool) -> None:
        """Style one reply action according to role and active theme.

        Args:
            button: Button to style.
            primary: Whether the action is the primary operation.
            dark: Whether the active theme is dark.

        Returns:
            None: The button stylesheet is replaced in place.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if primary:
            colors = "color: white; background: #d946a0; border: 1px solid #f88dcc;"

        # Conditional check: evaluate domain preconditions and invariants
        elif dark:
            colors = "color: #fff4fb; background: #302832; border: 1px solid #d9bfd0;"

        else:
            colors = "color: #6f3158; background: #fff8fd; border: 1px solid #d99abb;"

        button.setStyleSheet(
            f"QPushButton {{ {colors} border-radius: 14px; padding: 3px 9px; font: 700 9pt Arial; }}"
            "QPushButton:hover { background: #f062b7; color: white; border-color: #f062b7; }"
            + (
                "QPushButton:disabled { color: #82727d; background: #292229; border-color: #5f515a; }"

                # Conditional check: evaluate domain preconditions and invariants
                if dark
                else "QPushButton:disabled { color: #bca6b3; background: #f2eaf0; border-color: #dfd1da; }"
            )
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the themed rounded composer surface.

        Args:
            event: Qt paint event.

        Returns:
            None: The rounded themed surface is painted in the widget.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Clear
        )
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceOver
        )

        handle_inset = 6
        body_width = self.width() - handle_inset * 2
        body_height = self.height() - handle_inset * 2
        body = QRectF(
            handle_inset,
            handle_inset,
            body_width,
            body_height,
        )
        path = QPainterPath()
        path.addRoundedRect(body, 18, 18)
        dark = self._theme_mode == "dark"

        painter.setPen(QPen(QColor("#ff74c4" if dark else "#f062b7"), 3))
        painter.setBrush(QColor("#1f1722" if dark else "#fff8fd"))
        painter.drawPath(path)

        # Conditional check: evaluate domain preconditions and invariants
        if self._hover_corner:
            handle_centers = {
                "nw": body.topLeft(),
                "ne": body.topRight(),
                "sw": body.bottomLeft(),
                "se": body.bottomRight(),
            }
            painter.setPen(QPen(QColor("#1f1722" if dark else "#ffffff"), 2))
            painter.setBrush(QColor("#f062b7"))
            painter.drawEllipse(handle_centers[self._hover_corner], 5.0, 5.0)

        painter.end()
