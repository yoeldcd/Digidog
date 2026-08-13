"""Composition façade for the modular avatar-styled Qt reply composer."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from brain.presentation.avatar.qt.reply_window.controller import AvatarReplyController
from brain.presentation.avatar.communication.contracts.models import (
    CodexThreadTargetDTO,
    DeliveryMode,
)
from .actions import QtReplyWindowActionsMixin
from .geometry import QtReplyWindowGeometryMixin
from .style import QtReplyWindowStyleMixin


class _ReplyStatusLabel(QLabel):
    """Show the status row only while it contains a visible message."""

    def __init__(self, parent: QWidget) -> None:
        """Initialize a collapsed status row.

        Args:
            parent: Composer widget that owns the status row.

        Returns:
            None: The empty status row starts hidden.
        """
        super().__init__("", parent)
        self.hide()

    def setText(self, text: str) -> None:  # noqa: N802 - Qt API
        """Update status text and collapse the row when it is empty.

        Sets the label text content, adjusts row visibility based on presence of text,
        and triggers minimum window size recalculations.

        Args:
            text (str): Status text to display in the composer label.

        Returns:
            None: Label content and window layout minimum height are updated.
        """
        super().setText(text)
        self.setVisible(bool(text))

        owner = self.parentWidget()
        refresh_minimum_size = getattr(owner, "_refresh_chrome_minimum_size", None)

        # Conditional check: evaluate domain preconditions and invariants
        if callable(refresh_minimum_size):
            refresh_minimum_size()

    def clear(self) -> None:
        """Clear the status and collapse its layout row.

        Resets the status label text to an empty string, collapsing the status row
        and updating window size constraints.

        Args:
            None.

        Returns:
            None: Status label text is cleared.
        """
        self.setText("")


class QtReplyWindow(
    QtReplyWindowGeometryMixin,
    QtReplyWindowActionsMixin,
    QtReplyWindowStyleMixin,
    QWidget,
):
    """Compose the reply window from lifecycle, geometry, and style mixins.

    Attributes:
        _controller: Asynchronous reply coordinator.
        _target: Immutable target captured on open.
        _clipboard_attachment_instance_id: Saved clipboard-image marker bound to the target.
        _terminal_action_pending: Whether one terminal request is in flight.
        _terminal_state: Terminal state won by the captured instance.
        _manual_geometry: User-selected position and size to retain.
        _theme_mode: Active light or dark theme identifier.
        screenshotRequested: Signal emitted when the screenshot action is requested.
    """

    screenshotRequested = Signal()

    def __init__(self, controller: AvatarReplyController) -> None:
        """Initialize the detached composer and its keyboard actions.

        Args:
            controller: Reply coordinator used for delivery.

        Returns:
            None: The composer is ready to bind a conversation target.
        """
        window_flags = Qt.WindowType.Tool
        window_flags |= Qt.WindowType.WindowStaysOnTopHint
        window_flags |= Qt.WindowType.FramelessWindowHint
        super().__init__(None, window_flags)

        self._controller: AvatarReplyController = controller
        self._target: CodexThreadTargetDTO | None = None
        self._clipboard_attachment_instance_id: str | None = None
        self._hold_pending: bool = False
        self._hold_live: bool = True
        self._terminal_action_pending: bool = False
        self._terminal_action: str = ""
        self._terminal_state: str = ""
        self._drag_pointer: QPoint | None = None
        self._drag_origin: QPoint | None = None
        self._manual_geometry: QRect | None = None
        self._resize_origin: tuple[str, QPoint, QRect] | None = None
        self._hover_corner: str = ""
        self._applying_geometry: bool = False
        self._theme_mode: str = "light"
        self._chrome_minimum_size: QSize = QSize(320, 92)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle("Responder a Codex")
        self.setMinimumSize(320, 92)
        self._applying_geometry = True
        self.resize(570, 270)
        self._applying_geometry = False
        self.setMouseTracking(True)

        self.title_label = QLabel("Responder a Codex", self)
        self.title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #251a28; background: transparent;")

        self.close_button = QToolButton(self)
        self.close_button.setText("×")
        self.close_button.setAccessibleName("Cerrar respuesta")
        self.close_button.setFixedSize(28, 28)
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setStyleSheet(
            "QToolButton { color: #251a28; background: transparent; border: 0; font: 700 18px Arial; }"
            "QToolButton:hover { color: #d62839; background: rgba(214,40,57,18); border-radius: 14px; }"
        )
        self.close_button.clicked.connect(self._close_requested)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.close_button)

        self.target_label = QLabel("🧵 Sin conversación asociada", self)
        self.target_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.target_label.setStyleSheet("color: #6f3158; background: transparent;")

        self.editor = QTextEdit(self)
        self.editor.setPlaceholderText("Escribe tu mensaje para este task de Codex…")
        self.editor.setFont(QFont("Arial", 11))
        self.editor.setMinimumHeight(80)
        self.editor.setStyleSheet(
            "QTextEdit { color: #251a28; background: #ffffff; border: 1px solid #dfbfd2; "
            "border-radius: 12px; padding: 10px; selection-background-color: #f062b7; }"
            "QTextEdit:focus { border: 2px solid #f062b7; padding: 9px; }"
        )

        self.status_label = _ReplyStatusLabel(self)
        self.status_label.setWordWrap(True)
        self.status_label.setFont(QFont("Arial", 9))
        self.status_label.setStyleSheet(
            "color: #765568; background: transparent; padding: 0 3px;"
        )

        self.screenshot_button = self._action_button("📷 SCREENSHOT", primary=False)
        self.screenshot_button.setAccessibleName("SCREENSHOT")
        self.screenshot_button.setToolTip("Solicitar una captura de pantalla")
        self.screenshot_button.clicked.connect(self._screenshot_requested)

        self.yes_button = self._action_button("✅ YES", primary=False)
        self.yes_button.setAccessibleName("YES")
        self.yes_button.setToolTip("Enviar una respuesta afirmativa")
        self.yes_button.clicked.connect(self._submit_yes)

        self.not_button = self._action_button("❌ NOT", primary=False)
        self.not_button.setAccessibleName("NOT")
        self.not_button.setToolTip("Enviar una respuesta negativa")
        self.not_button.clicked.connect(self._submit_not)

        self.steer_button = self._action_button("💭 ENVIAR", primary=True)
        self.steer_button.setAccessibleName("ENVIAR")
        self.steer_button.setToolTip("Enviar ahora · Ctrl+Enter")
        self.steer_button.clicked.connect(self._submit_steer)

        self._action_buttons = (
            self.screenshot_button,
            self.yes_button,
            self.not_button,
            self.steer_button,
        )

        self.actions_footer = QWidget(self)
        self.actions_footer.setFixedHeight(32)
        self.actions_footer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        actions = QHBoxLayout(self.actions_footer)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        actions.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Loop execution: iterate over items
        for button in self._action_buttons:
            actions.addWidget(button, 1, Qt.AlignmentFlag.AlignVCenter)

        self.actions_layout = actions

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 10)
        layout.setSpacing(2)
        layout.addLayout(header)
        layout.addWidget(self.target_label)
        layout.addWidget(self.editor, 1)
        layout.addWidget(self.status_label)
        layout.addWidget(self.actions_footer)
        self._chrome_minimum_size = self._calculate_chrome_minimum_size()
        self.setMinimumSize(self._chrome_minimum_size)
        self._controller.deliveryFinished.connect(self._delivery_finished)

        # Conditional check: evaluate domain preconditions and invariants
        if hasattr(self._controller, "composerOpened"):
            self._controller.composerOpened.connect(self._composer_opened)

        self.send_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.send_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.send_shortcut.activated.connect(self._submit_steer)
        self.send_keypad_shortcut = QShortcut(QKeySequence("Ctrl+Enter"), self)
        self.send_keypad_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.send_keypad_shortcut.activated.connect(self._submit_steer)
        self._set_actions_enabled(False)
        self.set_theme("light")

    def _refresh_chrome_minimum_size(self) -> None:
        """Recalculate the minimum window size after status-row visibility changes.

        Returns:
            None: The window minimum follows the current visible chrome rows.
        """
        self._chrome_minimum_size = self._calculate_chrome_minimum_size()
        self.setMinimumSize(self._chrome_minimum_size)

    def is_target_active(self, target: CodexThreadTargetDTO) -> bool:
        """Return whether one exact target still owns a live composer hold.

        Args:
            target: Immutable target captured by a screenshot session.

        Returns:
            bool: True only while the same instance remains editable.
        """

        # Conditional check: evaluate domain preconditions and invariants
        if self._target is None:

            return False

        # Identity validation: check canonical message or instance identifier
        if self._target.instance_id != target.instance_id:

            return False

        # Conditional check: evaluate domain preconditions and invariants
        if not self._hold_live:

            return False

        # Conditional check: evaluate domain preconditions and invariants
        if self._hold_pending:

            return False

        # Conditional check: evaluate domain preconditions and invariants
        if self._terminal_action_pending:

            return False

        # State guard: verify component lifecycle state preconditions
        if self._terminal_state:

            return False

        return True
