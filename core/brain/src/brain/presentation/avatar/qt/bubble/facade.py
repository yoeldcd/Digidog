# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Thin public facade for the detached Qt Markdown bubble."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QSizePolicy, QTextBrowser, QToolButton,
    QVBoxLayout, QWidget,
)

from brain.presentation.avatar.interactivity.markdown_document import (
    AVATAR_BASE_FONT_POINTS, AVATAR_DOCUMENT_CSS,
)
from brain.presentation.avatar.qt.bubble.chrome import QtBubbleChromeMixin
from brain.presentation.avatar.qt.bubble.geometry import (
    QtBubbleGeometryMixin, UNBOUNDED_WIDGET_HEIGHT,
)
from brain.presentation.avatar.qt.markdown.styling import QtDocumentStylingMixin
from brain.presentation.avatar.qt.markdown.document import (
    AvatarTextBrowser, normalized_image_size, semantic_token_ranges,
    table_column_percentages,
)
from brain.presentation.avatar.qt.markdown.rendering import render_avatar_markdown


class QtMarkdownBubble(
    QtDocumentStylingMixin, QtBubbleChromeMixin, QtBubbleGeometryMixin, QWidget,
):
    """Compose document, styling, chrome, and geometry collaborators."""

    geometryChanged = Signal()
    dismissed = Signal()
    navigateRequested = Signal(int)
    replyRequested = Signal()
    manuallyMoved = Signal()

    def __init__(self) -> None:
        """Initialize frameless translucent avatar speech bubble widget.

        Returns:
            None.
        """
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(320, 156)
        screen = QApplication.primaryScreen()
        screen_height = screen.availableGeometry().height() if screen else 720
        self._standard_maximum_height = max(220, min(420, round(screen_height * .58)))
        self.setMaximumHeight(self._standard_maximum_height)
        self.resize(620, 180)
        self._drag_origin: tuple[QPoint, QPoint] | None = None
        self._resize_origin: tuple[str, QPoint, object] | None = None
        self._tail_target = QPointF(self.width() - 40, self.height() + 40)
        self._manual_size = False
        self._hover_corner = ""
        self._header_emotion = ""
        self._header_consumer_path = ""
        self._placed_above = True
        self._theme_mode = "light"
        self._zoom_step = 0
        self._last_image_dimensions: dict[str, tuple[int | None, int | None]] = {}
        self._footer_actions_on_right = False
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(80)
        self._hover_timer.timeout.connect(self._sync_resize_hover)
        self._hover_timer.start()

        self.document_view = AvatarTextBrowser(self)
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
        default_font = QFont("Arial")
        default_font.setPointSizeF(AVATAR_BASE_FONT_POINTS)
        self.document_view.document().setDefaultFont(default_font)
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
        self.backward_button = self._navigation_button("\u2039", "Mensaje anterior", -1)
        self.history_label = QLabel("1/1", self.footer)
        self.history_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_label.setFixedWidth(40)
        self.history_label.setStyleSheet("color: #765568; font: 700 10pt Arial; background: transparent;")
        self.forward_button = self._navigation_button("\u203a", "Mensaje siguiente", 1)
        self.remaining_label = QLabel("00:00", self.footer)
        self.remaining_label.setAccessibleName("Tiempo restante del mensaje")
        self.remaining_label.setMinimumWidth(self.remaining_label.fontMetrics().horizontalAdvance("00:00") + 12)
        self.remaining_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.remaining_label.setStyleSheet(
            "color: #765568; font: 700 10pt 'Consolas'; background: transparent;",
        )
        self.reply_button = self._reply_button()
        self.zoom_out_button = self._zoom_button("-", "Reducir mensaje", -1)
        self.zoom_in_button = self._zoom_button("+", "Ampliar mensaje", 1)
        self.footer_layout = QHBoxLayout(self.footer)
        self.footer_layout.setContentsMargins(0, 0, 0, 0)
        self.footer_layout.setSpacing(6)
        self._rebuild_footer_layout(False)
        footer_minimum = self.footer.sizeHint().width()
        horizontal_margins = 30 + 34
        self.setMinimumWidth(max(self.minimumWidth(), footer_minimum + horizontal_margins))

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
        self.set_theme("light")

    def set_message(
        self,
        text: str,
        emotion_prefix: str = "",
        consumer_path: str = "",
        history_index: int = 0,
        history_total: int = 1,
    ) -> None:
        """Render semantic Markdown without executing external links.

        Args:
            text (str): Rich Markdown content.
            emotion_prefix (str): Optional leading emotion annotation.
            consumer_path (str): Source consumer path for provenance.
            history_index (int): Zero-based visible-message history index.
            history_total (int): Total visible-message history count.
        """
        self._set_header(emotion_prefix, consumer_path, history_index, history_total)
        rendered = render_avatar_markdown(self, text, consumer_path)
        self._last_image_dimensions = rendered.image_dimensions
        self._fit_content_height()

