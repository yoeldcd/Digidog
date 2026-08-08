"""Modern compact widgets and styling for the Qt backlog presentation."""
from __future__ import annotations

from PySide6.QtCore import QStringListModel, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

from brain.presentation.avatar.qt.backlog.presentation.icons import STATUS_ICON_NAMES, svg_icon
from brain.presentation.avatar.qt.backlog.contracts.models import (
    BacklogThemeTokens,
    TaskStatus,
    TaskView,
)


class SuggestionComboBox(QComboBox):
    """Editable hierarchical domain picker with popup-only completion."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Configure an editable popup completer for hierarchical domains.

        Args:
            parent: Optional Qt owner for the combo box.
        """
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._suggestions: tuple[str, ...] = ()
        self._completion_model = QStringListModel(self)
        completer = QCompleter(self._completion_model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchStartsWith)
        self.setCompleter(completer)
        self.lineEdit().textEdited.connect(self._filter_hierarchically)

    def set_suggestions(self, suggestions: tuple[str, ...]) -> None:
        """Replace project-local domains without mutating the typed value.

        Args:
            suggestions: Candidate hierarchical domains from the selected project.

        Returns:
            None.
        """
        current = self.currentText()
        self._suggestions = tuple(
            dict.fromkeys(item.strip() for item in suggestions if item.strip())
        )
        self.blockSignals(True)
        self.clear()
        self.addItems(self._suggestions)
        self.setEditText(current)
        self.blockSignals(False)
        self._completion_model.setStringList(list(self._suggestions))

    def filtered_suggestions(self, typed: str) -> tuple[str, ...]:
        """Match every typed dot level against the same candidate level.

        Args:
            typed: Partial domain entered in the editable field.

        Returns:
            tuple[str, ...]: Candidate domains matching each entered segment.
        """
        value = typed.strip().casefold()
        if not value:
            return self._suggestions
        typed_levels = value.split(".")
        matches = []
        for candidate in self._suggestions:
            levels = candidate.casefold().split(".")
            if len(levels) < len(typed_levels):
                continue
            if all(levels[index].startswith(level) for index, level in enumerate(typed_levels)):
                matches.append(candidate)
        return tuple(matches)

    def _filter_hierarchically(self, typed: str) -> None:
        """Refresh the completer popup after each hierarchical text edit.

        Args:
            typed: Current text emitted by the editable line edit.

        Returns:
            None.
        """
        matches = self.filtered_suggestions(typed)
        self._completion_model.setStringList(list(matches))
        completer = self.completer()
        completer.setCompletionPrefix("")
        if matches:
            completer.complete()

    def setText(self, text: str) -> None:  # noqa: N802
        """Set the visible domain text through the editable combo API.

        Args:
            text: Domain value displayed in the line edit.

        Returns:
            None.
        """
        self.setEditText(text)

    def text(self) -> str:
        """Return the current editable domain value.

        Returns:
            str: Text currently shown in the combo box.
        """
        return self.currentText()


class DomainHeader(QWidget):
    """Visually separate one project-local task domain with toggle expand/collapse."""

    HEADER_HEIGHT = 24
    toggled = Signal(str, bool)

    def __init__(
        self,
        domain: str,
        task_count: int,
        theme: BacklogThemeTokens,
        parent: QWidget | None = None,
        expanded: bool = True,
    ) -> None:
        """Create a compact domain heading with a round count badge and toggle indicator.

        Args:
            domain: Domain label shown at the start of the task group.
            task_count: Number of visible tasks in the group.
            theme: Theme tokens used for heading contrast.
            parent: Optional Qt owner for the heading widget.
            expanded: Whether the task group under this domain is expanded.
        """
        super().__init__(parent)
        self.domain = domain
        self.expanded = expanded
        self._theme = theme
        self.setObjectName("domainHeader")
        self.setFixedHeight(self.HEADER_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.chevron = QLabel(self)
        self.chevron.setObjectName("domainHeaderChevron")
        self.chevron.setFixedWidth(16)
        self.chevron.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(domain, self)
        label.setObjectName("domainHeaderLabel")

        self.task_count_label = QLabel(str(task_count), self)
        self.task_count_label.setObjectName("domainHeaderCount")
        self.task_count_label.setFixedSize(18, 18)
        self.task_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(6)
        layout.addWidget(self.chevron)
        layout.addWidget(label)
        layout.addStretch(1)
        layout.addWidget(self.task_count_label)
        self.apply_theme(theme)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Toggle collapsed/expanded state when header is clicked."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_expanded()
            event.accept()
        else:
            super().mousePressEvent(event)

    def toggle_expanded(self) -> None:
        """Toggle expanded state and notify listeners."""
        self.set_expanded(not self.expanded)

    def set_expanded(self, expanded: bool, notify: bool = True) -> None:
        """Set expanded state and update visual chevron indicator.

        Args:
            expanded: True if domain task items should be visible.
            notify: Whether to emit the toggled signal.
        """
        if self.expanded == expanded:
            return
        self.expanded = expanded
        self.apply_theme(self._theme)
        if notify:
            self.toggled.emit(self.domain, self.expanded)

    def apply_theme(self, theme: BacklogThemeTokens) -> None:
        """Apply theme colors, round badge geometry, and chevron icon to the domain header.

        Args:
            theme: Palette inherited from the avatar theme mode.

        Returns:
            None.
        """
        self._theme = theme
        icon_name = "chevronDown" if self.expanded else "chevronRight"
        self.chevron.setPixmap(svg_icon(icon_name, theme.accent, 14).pixmap(14, 14))
        self.setStyleSheet(
            f"""
            QWidget#domainHeader {{
                background: {theme.surface_alt};
                border: 0;
                border-bottom: 1px solid {theme.border};
                border-radius: 5px;
            }}
            QWidget#domainHeader:hover {{
                background: {theme.selected};
            }}
            QLabel#domainHeaderLabel {{
                color: {theme.text};
                background: transparent;
                border: 0;
                font: 700 8pt 'Segoe UI';
            }}
            QLabel#domainHeaderCount {{
                color: {theme.muted};
                background: {theme.surface};
                border: 1px solid {theme.border};
                border-radius: 9px;
                font: 700 7pt 'Segoe UI';
            }}
            """,
        )

    def set_task_count(self, task_count: int) -> None:
        """Update the visible task count without replacing the header widget.

        Args:
            task_count: Number of currently visible tasks in this domain.

        Returns:
            None.
        """
        self.task_count_label.setText(str(task_count))


class TaskCard(QWidget):
    """Dense horizontal identity and detail affordance for one task."""

    ROW_HEIGHT = 40

    def __init__(
        self,
        task: TaskView,
        theme: BacklogThemeTokens,
        parent: QWidget | None = None,
    ) -> None:
        """Create one dense task row with status and priority affordances.

        Args:
            task: Immutable task projection rendered by the card.
            theme: Palette inherited from the avatar theme mode.
            parent: Optional Qt owner for the card widget.
        """
        super().__init__(parent)
        self._theme = theme
        self.task = task
        self.setObjectName("taskCard")
        self.setAccessibleName(
            f"{task.task_id}, {task.status.value}, {task.priority}, {task.domain}, {task.title}",
        )
        self.setToolTip(f"Open {task.task_id}: {task.title}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(self.ROW_HEIGHT)

        self.status_icon = QLabel(self)
        self.status_icon.setObjectName("statusIcon")
        self.status_icon.setAccessibleName(f"{task.status.value} status")
        self.status_icon.setToolTip(task.status.value)
        self.status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_icon.setFixedWidth(20)

        self.task_id_label = QLabel(task.task_id, self)
        self.task_id_label.setObjectName("taskId")
        self.task_id_label.setFixedWidth(46)
        self.title_label = QLabel(task.title, self)
        self.title_label.setObjectName("title")
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.status_badge = QLabel(task.status.value, self)
        self.status_badge.setObjectName("statusBadge")
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setFixedSize(66, 20)
        self.priority_badge = QLabel(str(task.priority).upper(), self)
        self.priority_badge.setObjectName("priorityBadge")
        self.priority_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.priority_badge.setFixedSize(54, 20)
        self.chevron = QLabel(self)
        self.chevron.setObjectName("detailChevron")
        self.chevron.setAccessibleName("Open task details")
        self.chevron.setToolTip("Open task details")
        self.chevron.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chevron.setFixedWidth(18)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 6, 2)
        layout.setSpacing(6)
        layout.addWidget(self.status_icon)
        layout.addWidget(self.task_id_label)
        layout.addWidget(self.title_label, 1)
        layout.addWidget(self.status_badge)
        layout.addWidget(self.priority_badge)
        layout.addWidget(self.chevron)
        self.apply_theme(theme)

    def apply_theme(self, theme: BacklogThemeTokens) -> None:
        """Apply normalized badges and Explorer-derived semantic SVG icons.

        Args:
            theme: Palette used to derive badge and icon contrast.

        Returns:
            None.
        """
        self._theme = theme
        status_color = {
            TaskStatus.TODO: theme.muted,
            TaskStatus.WORKING: "#087b99" if theme.mode == "light" else "#6bd9f5",
            TaskStatus.DONE: "#247747" if theme.mode == "light" else "#72d69c",
        }[self.task.status]
        priority_color = {
            "HIGH": "#a51f31" if theme.mode == "light" else "#ff8c98",
            "MEDIUM": "#765000" if theme.mode == "light" else "#ffd074",
            "LOW": theme.muted,
        }.get(str(self.task.priority).upper(), theme.muted)
        icon_name = STATUS_ICON_NAMES[self.task.status.value]
        self.status_icon.setPixmap(svg_icon(icon_name, status_color, 17).pixmap(17, 17))
        self.chevron.setPixmap(svg_icon("chevronRight", theme.accent, 16).pixmap(16, 16))
        self.setStyleSheet(
            f"""
            QWidget#taskCard {{
                background: {theme.surface};
                border: 1px solid {theme.border};
                border-radius: 5px;
            }}
            QWidget#taskCard:hover {{
                background: {theme.selected};
                border: 2px solid {theme.accent};
            }}
            QLabel {{
                color: {theme.text};
                background: transparent;
                border: 0;
            }}
            QLabel#taskId {{
                color: {theme.muted};
                font: 700 8pt 'Consolas';
            }}
            QLabel#title {{
                color: {theme.text};
                font: 600 9pt 'Segoe UI';
            }}
            QLabel#statusBadge, QLabel#priorityBadge {{
                border-radius: 6px;
                font: 700 7pt 'Segoe UI';
            }}
            QLabel#statusBadge {{
                color: {status_color};
                background: {theme.surface_alt};
                border: 1px solid {status_color};
            }}
            QLabel#priorityBadge {{
                color: {priority_color};
                background: {theme.surface_alt};
                border: 1px solid {priority_color};
            }}
            """,
        )

    def update_task(self, task: TaskView) -> None:
        """Update the rendered task projection without replacing this card.

        Args:
            task: New immutable task projection. Its task_id must match the
                existing task_id so this QWidget identity remains stable.

        Returns:
            None.
        """
        self.task = task
        self.setAccessibleName(
            f"{task.task_id}, {task.status.value}, {task.priority}, {task.domain}, {task.title}",
        )
        self.setToolTip(f"Open {task.task_id}: {task.title}")
        self.status_icon.setAccessibleName(f"{task.status.value} status")
        self.status_icon.setToolTip(task.status.value)
        self.task_id_label.setText(task.task_id)
        self.title_label.setText(task.title)
        self.status_badge.setText(task.status.value)
        self.priority_badge.setText(str(task.priority).upper())
        self.apply_theme(self._theme)


def backlog_stylesheet(theme: BacklogThemeTokens) -> str:
    """Return the intentional modern shell stylesheet for one theme.

    Args:
        theme: Palette tokens interpolated into the stylesheet.

    Returns:
        str: Qt stylesheet for the list, filters, task cards, and task form.
    """
    return f"""
    QDialog#backlogWindow {{
        background: {theme.background};
        color: {theme.text};
    }}
    QDialog#backlogWindow QLabel, QDialog#backlogWindow QGroupBox {{
        color: {theme.text};
    }}
    QWidget#listPage {{
        background: {theme.background};
    }}
    QDialog#backlogWindow QComboBox,
    QDialog#backlogWindow QLineEdit,
    QDialog#backlogWindow QTextEdit,
    QDialog#backlogWindow QListWidget {{
        color: {theme.text};
        background: {theme.surface};
        border: 1px solid {theme.border};
        border-radius: 6px;
        padding: 4px;
        selection-background-color: {theme.selected};
        selection-color: {theme.text};
    }}
    QDialog#backlogWindow QComboBox:focus,
    QDialog#backlogWindow QLineEdit:focus,
    QDialog#backlogWindow QTextEdit:focus {{
        border: 2px solid {theme.accent};
    }}
    QDialog#backlogWindow QListWidget {{
        padding: 4px;
        border: 2px solid {theme.border};
    }}
    QDialog#backlogWindow QComboBox::drop-down {{
        width: 26px;
        border-left: 1px solid {theme.border};
        background: {theme.surface_alt};
    }}
    QDialog#backlogWindow QGroupBox {{
        border: 1px solid {theme.border};
        border-radius: 7px;
        margin-top: 14px;
        margin-bottom: 0px;
        padding-top: 3px;
        padding-bottom: 2px;
        font: 700 8pt 'Segoe UI';
        background: {theme.surface_alt};
    }}
    QDialog#backlogWindow QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
        color: {theme.muted};
    }}
    QDialog#backlogWindow QPushButton {{
        color: {theme.text};
        background: {theme.surface_alt};
        border: 2px solid {theme.border};
        border-radius: 7px;
        padding: 5px 9px;
        font: 700 8pt 'Segoe UI';
    }}
    QDialog#backlogWindow QPushButton:hover {{
        color: {theme.text};
        background: {theme.selected};
        border: 2px solid {theme.accent_hover};
    }}
    QDialog#backlogWindow QPushButton:pressed {{
        color: {theme.text};
        background: {theme.border};
        border-color: {theme.accent};
    }}
    QDialog#backlogWindow QPushButton:checked {{
        color: {theme.accent_text};
        background: {theme.accent};
        border: 2px solid {theme.accent_hover};
    }}
    QDialog#backlogWindow QPushButton[compactAction="true"] {{
        min-width: 30px;
        max-width: 30px;
        min-height: 28px;
        max-height: 28px;
        padding: 0;
    }}
    QDialog#backlogWindow QPushButton[filterOption="true"] {{
        min-width: 88px;
        max-width: 88px;
        min-height: 28px;
        max-height: 28px;
        padding: 0 5px;
    }}
    QDialog#backlogWindow QPushButton[primaryAction="true"] {{
        color: {theme.accent_text};
        background: {theme.accent};
        border-color: {theme.accent};
    }}
    QDialog#backlogWindow QPushButton:disabled {{
        color: {theme.muted};
        background: {theme.surface};
        border-color: {theme.border};
    }}
    QWidget#taskForm {{
        background: {theme.surface};
        border: 2px solid {theme.border};
        border-radius: 9px;
    }}
    QLabel#formHeading {{
        color: {theme.accent};
        background: {theme.surface_alt};
        border: 0;
        border-left: 5px solid {theme.accent};
        border-radius: 7px;
        padding: 9px 12px;
        font: 700 14pt 'Segoe UI';
    }}
    QDialog#backlogWindow QLineEdit#taskSearch {{
        margin-top: 0px;
        margin-bottom: 0px;
        min-height: 30px;
        max-height: 30px;
        border-radius: 7px;
        padding: 0 4px;

        font: 600 9pt 'Segoe UI';
    }}
    QWidget#taskForm > QLabel {{
        color: {theme.text};
        background: transparent;
        border: 0;
        border-bottom: 1px solid {theme.border};
        padding-bottom: 1px;
        font: 700 8pt 'Segoe UI';
    }}
    QLabel#captureState {{
        color: {theme.muted};
    }}
    """


def popup_stylesheet(theme: BacklogThemeTokens) -> str:
    """Force contrast in native combo/completer popup views.

    Args:
        theme: Palette tokens used by the popup foreground and selection.

    Returns:
        str: Qt stylesheet applied to native popup item views.
    """
    return (
        f"QAbstractItemView {{ color: {theme.text}; background: {theme.surface}; "
        f"border: 2px solid {theme.border}; outline: 0; "
        f"selection-color: #ffffff; selection-background-color: {theme.accent}; }}"
    )
