"""Fixed native Qt sidebar composition for backlog annotations."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QGroupBox,
    QLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from brain.presentation.avatar.qt.backlog.contracts.models import BacklogThemeTokens
from brain.presentation.avatar.qt.backlog.presentation.icons import configure_button


SIDEBAR_WIDTH = 252
"""Fixed annotation sidebar width in device-independent pixels."""

_TOOL_SPECIFICATIONS: tuple[tuple[str, str, str, str], ...] = (
    ("rectangle", "Rectangle", "Draw a rectangle annotation", "checkSquare"),
    ("arrow", "Arrow", "Draw an arrow annotation", "chevronRight"),
    ("path", "Freehand", "Draw a freehand path annotation", "edit"),
    ("label", "Label", "Place a text label annotation", "messageCircle"),
)
"""Immutable presentation metadata for annotation tool actions."""


class AnnotationSidebar(QScrollArea):
    """Own fixed-width annotation controls without knowing editor state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize editor actions and compose the scrolling sidebar.

        Args:
            parent: Optional Qt owner for the sidebar.
        """
        super().__init__(parent)
        self.setObjectName("annotationSidebar")
        self.setAccessibleName("Annotation controls")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        self._tokens: BacklogThemeTokens | None = None
        self._color = "#ff3b30"
        self._content = QWidget(self)
        self._content.setObjectName("annotationSidebarContent")

        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_buttons = self._create_tool_buttons()
        self.color_button = self._create_button()
        self.label_input = QLineEdit("LABEL", self._content)
        self.copy_button = self._create_button()
        self.undo_button = self._create_button()
        self.redo_button = self._create_button()
        self.delete_button = self._create_button()
        self.clear_button = self._create_button()

        self._configure_label_input()
        self._build_layout()
        self.setWidget(self._content)

    def _create_button(self) -> QPushButton:
        """Create one consistently sized sidebar action.

        Returns:
            QPushButton: Unconfigured action owned by the sidebar content.
        """
        button = QPushButton(self._content)
        button.setMinimumHeight(36)
        return button

    def _create_tool_buttons(self) -> dict[str, QPushButton]:
        """Create the private tool-button registry and exclusive button group.

        Returns:
            dict[str, QPushButton]: Buttons keyed by annotation tool identifier.
        """
        buttons: dict[str, QPushButton] = {}

        for tool_id, (tool, _label, _tooltip, _icon_name) in enumerate(_TOOL_SPECIFICATIONS):
            button = self._create_button()
            button.setCheckable(True)
            self.tool_group.addButton(button, tool_id)
            buttons[tool] = button

        buttons["rectangle"].setChecked(True)
        return buttons

    def _configure_label_input(self) -> None:
        """Apply the label editor's visible and accessible identity.

        Returns:
            None.
        """
        self.label_input.setAccessibleName("Annotation label")
        self.label_input.setToolTip("Text for a new or selected label annotation")
        self.label_input.setPlaceholderText("Label text")
        self.label_input.setMinimumHeight(36)

    def _build_layout(self) -> None:
        """Compose tools, configuration, and state sections vertically.

        Returns:
            None.
        """
        tools_layout = QVBoxLayout()

        for tool, _label, _tooltip, _icon_name in _TOOL_SPECIFICATIONS:
            tools_layout.addWidget(self.tool_buttons[tool])

        configuration_layout = QVBoxLayout()
        configuration_layout.addWidget(self.color_button)
        configuration_layout.addWidget(self.label_input)

        state_layout = QGridLayout()
        state_layout.addWidget(self.undo_button, 0, 0)
        state_layout.addWidget(self.redo_button, 0, 1)
        state_layout.addWidget(self.delete_button, 1, 0)
        state_layout.addWidget(self.clear_button, 1, 1)
        state_layout.addWidget(self.copy_button, 2, 0, 1, 2)

        layout = QVBoxLayout(self._content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        configuration_state_layout = QVBoxLayout()
        configuration_state_layout.addLayout(configuration_layout)
        configuration_state_layout.addLayout(state_layout)

        layout.addWidget(self._create_group("Tools", tools_layout))
        layout.addWidget(self._create_group("Configuration/State", configuration_state_layout))
        layout.addStretch(1)

    def _create_group(self, title: str, controls: QLayout) -> QGroupBox:
        """Wrap one cohesive control layout in an accessible section.

        Args:
            title: Visible section title.
            controls: Layout containing the section's controls.

        Returns:
            QGroupBox: Sidebar section containing the supplied controls.
        """
        group = QGroupBox(title, self._content)
        group.setObjectName(f"annotation{title.replace("/", "")}Group")
        group.setAccessibleName(f"Annotation {title.lower()}")
        controls.setContentsMargins(7, 6, 7, 7)
        controls.setSpacing(6)
        group.setLayout(controls)
        return group

    def set_theme(self, tokens: BacklogThemeTokens) -> None:
        """Apply theme tokens to sidebar widgets and semantic SVG actions.

        Args:
            tokens: Avatar-derived annotation theme palette.

        Returns:
            None.
        """
        self._tokens = tokens
        self._configure_actions(tokens)
        self.setStyleSheet(
            f"""
            QScrollArea#annotationSidebar {{
                background: {tokens.surface_alt};
                border: 1px solid {tokens.border};
                border-radius: 8px;
            }}
            QWidget#annotationSidebarContent {{
                background: {tokens.surface_alt};
                color: {tokens.text};
            }}
            QScrollArea#annotationSidebar QGroupBox {{
                color: {tokens.text};
                background: {tokens.surface_alt};
                border: 1px solid {tokens.border};
                border-radius: 7px;
                margin-top: 8px;
                font-weight: 700;
            }}
            QScrollArea#annotationSidebar QGroupBox::title {{
                subcontrol-origin: margin;
                left: 7px;
                padding: 0 4px;
                color: {tokens.muted};
            }}
            QScrollArea#annotationSidebar QLineEdit {{
                color: {tokens.text};
                background: {tokens.surface};
                border: 1px solid {tokens.border};
                border-radius: 6px;
                padding: 6px;
            }}
            QScrollArea#annotationSidebar QPushButton {{
                color: {tokens.text};
                background: {tokens.surface};
                border: 1px solid {tokens.border};
                border-radius: 6px;
                padding: 6px;
                text-align: left;
            }}
            QScrollArea#annotationSidebar QPushButton:hover {{
                background: {tokens.selected};
                border: 2px solid {tokens.accent};
            }}
            QScrollArea#annotationSidebar QPushButton:checked {{
                color: #ffffff;
                background: {tokens.accent};
                border: 2px solid {tokens.accent_hover};
            }}
            QScrollArea#annotationSidebar QPushButton:disabled {{
                color: {tokens.muted};
                background: {tokens.surface_alt};
                border-color: {tokens.border};
            }}
            """,
        )

    def set_color(self, color: str) -> None:
        """Update the semantic color action without mutating annotation state.

        Args:
            color: Current annotation color represented by the action icon.

        Returns:
            None.
        """
        self._color = color

        if self._tokens is None:
            return

        self._configure_color_action(self._tokens)

    def _configure_actions(self, tokens: BacklogThemeTokens) -> None:
        """Configure complete icon, tooltip, and accessibility action states.

        Args:
            tokens: Theme palette used for normal, checked, and disabled icons.

        Returns:
            None.
        """
        for tool, label, tooltip, icon_name in _TOOL_SPECIFICATIONS:
            configure_button(
                self.tool_buttons[tool],
                icon_name=icon_name,
                label=label,
                tooltip=tooltip,
                color=tokens.text,
                checked_color="#ffffff",
                disabled_color=tokens.muted,
            )

        self._configure_color_action(tokens)
        configure_button(
            self.copy_button,
            icon_name="copy",
            label="Copy",
            tooltip="Copy the annotated image to the clipboard",
            color=tokens.text,
            disabled_color=tokens.muted,
        )
        configure_button(
            self.undo_button,
            icon_name="chevronLeft",
            label="Undo",
            tooltip="Undo the last annotation change",
            color=tokens.text,
            disabled_color=tokens.muted,
        )
        configure_button(
            self.redo_button,
            icon_name="chevronRight",
            label="Redo",
            tooltip="Redo the last annotation change",
            color=tokens.text,
            disabled_color=tokens.muted,
        )
        configure_button(
            self.delete_button,
            icon_name="trash",
            label="Delete",
            tooltip="Delete the selected annotation",
            color=tokens.text,
            disabled_color=tokens.muted,
        )
        configure_button(
            self.clear_button,
            icon_name="close",
            label="Clear",
            tooltip="Clear all annotations",
            color=tokens.text,
            disabled_color=tokens.muted,
        )

    def _configure_color_action(self, tokens: BacklogThemeTokens) -> None:
        """Configure the color action with the selected annotation color.

        Args:
            tokens: Theme palette supplying the disabled icon color.

        Returns:
            None.
        """
        configure_button(
            self.color_button,
            icon_name="sliders",
            label="Color",
            tooltip="Select the annotation color",
            color=self._color,
            disabled_color=tokens.muted,
        )