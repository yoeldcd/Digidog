"""Dialog controller and capture export boundary for Qt backlog annotations."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from brain.presentation.avatar.qt.backlog.annotation.canvas import AnnotationCanvas
from brain.presentation.avatar.qt.backlog.annotation.sidebar import AnnotationSidebar
from brain.presentation.avatar.qt.backlog.contracts.models import BacklogThemeTokens, backlog_theme
from brain.presentation.avatar.qt.backlog.presentation.icons import configure_button


class AnnotationDialog(QDialog):
    """Coordinate the native annotation sidebar and transactional canvas editor."""

    def __init__(
        self,
        pixmap: QPixmap,
        parent: QWidget | None = None,
        theme: BacklogThemeTokens | str = "light",
    ) -> None:
        """Initialize the non-modal annotation editor and its action groups.

        Args:
            pixmap: Source-resolution screenshot shown in the annotation canvas.
            parent: Optional Qt owner for the editor window.
            theme: Avatar theme tokens or a theme name used to style the editor.
        """
        super().__init__(parent)
        self.setObjectName("annotationDialog")
        self.setWindowTitle("Annotate capture")
        self.setModal(False)
        self.resize(parent.size() if parent is not None else QSize(720, 620))
        self.canvas = AnnotationCanvas(pixmap, self)
        self.sidebar = AnnotationSidebar(self)
        self.tool_group = self.sidebar.tool_group
        self.tool_buttons = self.sidebar.tool_buttons
        self.color_button = self.sidebar.color_button
        self.label_input = self.sidebar.label_input
        self.copy_button = self.sidebar.copy_button
        self.delete_button = self.sidebar.delete_button
        self.clear_button = self.sidebar.clear_button
        self.undo_button = self.sidebar.undo_button
        self.redo_button = self.sidebar.redo_button
        self.close_button = QPushButton(self)
        self.close_button.setObjectName("annotationCancelButton")
        self.close_button.setMinimumSize(92, 36)
        self.save_button = QPushButton(self)
        self.save_button.setObjectName("annotationSaveButton")
        self.save_button.setMinimumSize(92, 36)
        self._tool_names = tuple(self.tool_buttons)
        self._active_tool = "rectangle"
        self.tool_group.idClicked.connect(self._on_tool_selected)
        self.color_button.clicked.connect(self.choose_color)
        self.label_input.textChanged.connect(self.canvas.set_label)
        self.copy_button.clicked.connect(self.copy_result_to_clipboard)
        self.delete_button.clicked.connect(self.canvas.delete_selected)
        self.clear_button.clicked.connect(self.canvas.clear_annotations)
        self.undo_button.clicked.connect(self.canvas.undo)
        self.redo_button.clicked.connect(self.canvas.redo)
        self.save_button.clicked.connect(self.accept)
        self.close_button.clicked.connect(self.reject)
        self.canvas.stateChanged.connect(self._sync_controls)
        self._build_layout()
        self.set_theme(theme)
        self._update_color_icon()
        self._sync_controls()
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

    def _build_layout(self) -> None:
        """Compose the sidebar beside a canvas with external window actions.

        Returns:
            None.
        """
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)
        action_layout.addStretch(1)
        action_layout.addWidget(self.close_button)
        action_layout.addWidget(self.save_button)

        workspace_layout = QVBoxLayout()
        workspace_layout.setSpacing(8)
        workspace_layout.addWidget(self.canvas, 1)
        workspace_layout.addLayout(action_layout)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(self.sidebar)
        layout.addLayout(workspace_layout, 1)

    def _configure_window_actions(self, tokens: BacklogThemeTokens) -> None:
        """Configure bottom-right window actions outside the annotation sidebar.

        Args:
            tokens: Theme palette used for action icon colors.

        Returns:
            None.
        """
        configure_button(
            self.close_button,
            icon_name="close",
            label="Cancel",
            tooltip="Cancel annotation editing",
            color=tokens.text,
            disabled_color=tokens.muted,
        )
        configure_button(
            self.save_button,
            icon_name="save",
            label="Save",
            tooltip="Save annotations and close the editor",
            color="#ffffff",
            disabled_color=tokens.muted,
        )

    def _on_tool_selected(self, tool_id: int) -> None:
        """Translate the sidebar's exclusive button identifier into a tool name.

        Args:
            tool_id: Stable button identifier assigned by the annotation sidebar.

        Returns:
            None.
        """
        if tool_id < 0 or tool_id >= len(self._tool_names):
            return

        self._select_tool(self._tool_names[tool_id])

    def _select_tool(self, tool: str) -> None:
        """Apply exclusive tool selection and update contextual text editing.

        Args:
            tool: Annotation tool identifier selected by the user.

        Returns:
            None.
        """
        self._active_tool = tool
        self.canvas.set_tool(tool)
        self._sync_controls()
        if tool == "label":
            self.label_input.setFocus(Qt.FocusReason.OtherFocusReason)

    def _sync_controls(self) -> None:
        """Project canvas selection/history into enabled sidebar actions.

        Returns:
            None.
        """
        selected = self.canvas.selected_mark
        label_context = self._active_tool == "label" or (
            selected is not None and selected.kind == "label"
        )
        self.label_input.setEnabled(label_context)
        if (
            selected is not None
            and selected.kind == "label"
            and self.label_input.text() != selected.label
        ):
            self.label_input.blockSignals(True)
            self.label_input.setText(selected.label)
            self.label_input.blockSignals(False)
        self.delete_button.setEnabled(self.canvas.has_selection)
        self.clear_button.setEnabled(bool(self.canvas.marks))
        self.undo_button.setEnabled(self.canvas.can_undo)
        self.redo_button.setEnabled(self.canvas.can_redo)

    def set_theme(self, theme: BacklogThemeTokens | str) -> None:
        """Apply avatar-derived theme tokens to the dialog and sidebar.

        Args:
            theme: Theme tokens or a theme name inherited from the avatar.

        Returns:
            None.
        """
        tokens = backlog_theme(theme) if isinstance(theme, str) else theme
        self.theme_tokens = tokens
        self.canvas.set_background(tokens.background)
        self.sidebar.set_theme(tokens)
        self._configure_window_actions(tokens)
        self.setStyleSheet(
            f"""
            QDialog#annotationDialog {{
                background: {tokens.background};
                color: {tokens.text};
            }}
            QPushButton#annotationCancelButton {{
                color: {tokens.text};
                background: {tokens.surface_alt};
                border: 1px solid {tokens.border};
                border-radius: 6px;
                padding: 6px;
            }}
            QPushButton#annotationCancelButton:hover {{
                background: {tokens.selected};
                border: 2px solid {tokens.accent};
            }}
            QPushButton#annotationSaveButton {{
                color: #ffffff;
                background: {tokens.accent};
                border: 1px solid {tokens.accent_hover};
                border-radius: 6px;
                padding: 6px;
            }}
            QPushButton#annotationSaveButton:hover {{
                background: {tokens.accent_hover};
            }}
            """,
        )

    def result_pixmap(self) -> QPixmap:
        """Return source-resolution marked content for the capture contract.

        Returns:
            QPixmap: Source-resolution image with all committed annotations.
        """
        return self.canvas.baked_pixmap()

    def copy_result_to_clipboard(self) -> None:
        """Copy the clean annotated result through the native Qt clipboard.

        Returns:
            None.
        """
        QApplication.clipboard().setPixmap(self.result_pixmap())

    def choose_color(self) -> None:
        """Open the sole color selector and reflect the accepted color action.

        Returns:
            None.
        """
        selected = QColorDialog.getColor(QColor(self.canvas._color), self, "Annotation color")
        if selected.isValid():
            self.canvas.apply_color(selected.name())
            self._update_color_icon()

    def _update_color_icon(self) -> None:
        """Render the current annotation color through the SVG action adapter.

        Returns:
            None.
        """
        self.sidebar.set_color(self.canvas._color)
