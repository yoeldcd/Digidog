# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Independent, avatar-styled Qt reply composer."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QPainterPath, QPen, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizeGrip, QTextEdit, QToolButton, QVBoxLayout, QWidget

from brain.presentation.avatar.communication.controller import AvatarReplyController
from brain.presentation.avatar.communication.models import CodexThreadTargetDTO, DeliveryMode, ReplyResultDTO


class QtReplyWindow(QWidget):
    """Detached composer that retains the avatar bubble's visual language."""

    def __init__(self, controller: AvatarReplyController) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint,
        )
        self._controller = controller
        self._target: CodexThreadTargetDTO | None = None
        self._drag_pointer: QPoint | None = None
        self._drag_origin: QPoint | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle("Responder a Codex")
        self.setMinimumSize(320, 92)
        self.resize(570, 270)

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
        self.close_button.clicked.connect(self.hide)

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
        self.editor.setStyleSheet(
            "QTextEdit { color: #251a28; background: #ffffff; border: 1px solid #dfbfd2; "
            "border-radius: 12px; padding: 10px; selection-background-color: #f062b7; }"
            "QTextEdit:focus { border: 2px solid #f062b7; padding: 9px; }"
        )
        self.status_label = QLabel("", self)
        self.status_label.setWordWrap(True)
        self.status_label.setFont(QFont("Arial", 9))
        self.status_label.setStyleSheet("color: #765568; background: transparent; padding: 0 3px;")

        self.queue_button = self._action_button("◷  Encolar", primary=False)
        self.queue_button.setToolTip("Enviar cuando termine el turno actual")
        self.steer_button = self._action_button("➤  Enviar", primary=True)
        self.steer_button.setToolTip("Enviar ahora · Ctrl+Enter")
        self.interrupt_button = self._action_button("■  Interrumpir", primary=False)
        self.interrupt_button.setToolTip("Interrumpir el turno actual y enviar")
        self.queue_button.clicked.connect(lambda: self._submit(DeliveryMode.QUEUE))
        self.steer_button.clicked.connect(lambda: self._submit(DeliveryMode.STEER))
        self.interrupt_button.clicked.connect(lambda: self._submit(DeliveryMode.INTERRUPT))
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.queue_button)
        actions.addWidget(self.steer_button)
        actions.addWidget(self.interrupt_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 14)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addWidget(self.target_label)
        layout.addWidget(self.editor, 1)
        layout.addWidget(self.status_label)
        layout.addLayout(actions)
        self.size_grip = QSizeGrip(self)
        self.size_grip.setStyleSheet("background: transparent; width: 14px; height: 14px;")
        self._controller.deliveryFinished.connect(self._delivery_finished)
        self.send_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.send_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.send_shortcut.activated.connect(lambda: self._submit(DeliveryMode.STEER))
        self.send_keypad_shortcut = QShortcut(QKeySequence("Ctrl+Enter"), self)
        self.send_keypad_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.send_keypad_shortcut.activated.connect(lambda: self._submit(DeliveryMode.STEER))
        self._set_actions_enabled(False)
        self.interrupt_button.setToolTip("No disponible: el canal nativo del host no expone interrupción")

    def _action_button(self, text: str, primary: bool) -> QPushButton:
        button = QPushButton(text, self)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(30)
        colors = (
            "color: white; background: #d946a0; border: 1px solid #d946a0;"
            if primary
            else "color: #6f3158; background: #fff8fd; border: 1px solid #d99abb;"
        )
        button.setStyleSheet(
            f"QPushButton {{ {colors} border-radius: 14px; padding: 3px 9px; font: 700 9pt Arial; }}"
            "QPushButton:hover { background: #f062b7; color: white; border-color: #f062b7; }"
            "QPushButton:disabled { color: #bca6b3; background: #f2eaf0; border-color: #dfd1da; }"
        )
        return button

    @property
    def target(self) -> CodexThreadTargetDTO | None:
        return self._target

    def open_for(self, target: CodexThreadTargetDTO) -> None:
        """Bind to one message target without following later incoming speaks."""
        self._target = target
        self.target_label.setText(f"🧵 Task {target.thread_id}")
        self.target_label.setToolTip(target.thread_id)
        self.status_label.clear()
        self._set_actions_enabled(True)
        self.show()
        self.raise_()
        self.activateWindow()
        self.editor.setFocus()

    def _submit(self, mode: DeliveryMode) -> None:
        if self._target is None or not self.editor.toPlainText().strip():
            self.status_label.setText("Escribe un mensaje antes de enviarlo.")
            return
        try:
            self._set_actions_enabled(False)
            self.status_label.setText("Enviando…")
            self._controller.submit(self._target, self.editor.toPlainText(), mode)
        except ValueError as exc:
            self._set_actions_enabled(True)
            self.status_label.setText(str(exc))

    def _delivery_finished(self, result: ReplyResultDTO) -> None:
        self._set_actions_enabled(True)
        if result.accepted:
            self.editor.clear()
            self.status_label.setText("✓ Referencia encolada para entrega nativa.")
            self.status_label.setStyleSheet("color: #248a62; background: transparent; padding: 0 3px;")
        else:
            self.status_label.setText(f"No se pudo entregar: {result.error}")
            self.status_label.setStyleSheet("color: #a33161; background: transparent; padding: 0 3px;")

    def _set_actions_enabled(self, enabled: bool) -> None:
        for button in (self.queue_button, self.steer_button):
            button.setEnabled(enabled)
        self.interrupt_button.setEnabled(False)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= 58:
            self._drag_pointer = event.globalPosition().toPoint()
            self._drag_origin = self.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._drag_pointer is not None and self._drag_origin is not None:
            self.move(self._drag_origin + event.globalPosition().toPoint() - self._drag_pointer)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._drag_pointer = None
        self._drag_origin = None
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self.size_grip.move(self.width() - self.size_grip.width() - 8, self.height() - self.size_grip.height() - 8)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        body = QRectF(2, 2, self.width() - 4, self.height() - 4)
        path = QPainterPath()
        path.addRoundedRect(body, 18, 18)
        painter.setPen(QPen(QColor("#f062b7"), 3))
        painter.setBrush(QColor("#fff8fd"))
        painter.drawPath(path)
        painter.end()
