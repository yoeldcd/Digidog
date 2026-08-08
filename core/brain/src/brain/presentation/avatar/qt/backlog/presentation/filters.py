"""Cohesive filter-control construction for the native Qt backlog."""
from __future__ import annotations

from collections.abc import Iterable
import re
from typing import TypeVar


from PySide6.QtWidgets import QButtonGroup, QGroupBox, QHBoxLayout, QPushButton, QWidget

from brain.presentation.avatar.qt.backlog.contracts.models import TaskPriority, TaskStatus, TaskView

FilterKey = TypeVar("FilterKey")


def matches_task_search(task: TaskView, query: str) -> bool:
    """Return whether one task matches the normalized search query.

    Args:
        task: Task projection searched by the list view.
        query: Case-folded text fragment entered by the user.

    Returns:
        bool: Whether the task title contains the query.
    """
    if not query:
        return True
    normalized_query = query.casefold()
    return normalized_query in task.title.casefold()


def task_date_key(task: TaskView) -> tuple[float, str]:
    """Sort by persisted creation time, with a stable legacy task-ID fallback.

    Args:
        task: Task projection whose timestamp or legacy ID is inspected.

    Returns:
        tuple[float, str]: Sort key combining creation order and task identity.
    """
    created_at = float(task.created_at or 0.0)
    if created_at <= 0:
        suffix = re.search(r"(\d+)$", task.task_id)
        created_at = float(suffix.group(1)) if suffix else 0.0
    return created_at, task.task_id.casefold()


class BacklogFilterBar(QWidget):
    """Own the normalized status, priority, and date filter controls."""

    def __init__(
        self,
        statuses: frozenset[TaskStatus],
        priorities: frozenset[TaskPriority],
        parent: QWidget | None = None,
        search_widget: QWidget | None = None,
    ) -> None:
        """Create grouped status, priority, date controls and optional search input.

        Args:
            statuses: Initially enabled task statuses.
            priorities: Initially enabled task priorities.
            parent: Optional Qt owner for the filter bar.
            search_widget: Optional search line edit placed in the filter bar row.
        """
        super().__init__(parent)
        self.status_buttons = self._group_buttons(
            "Status", "statusFilters", ((status, status in statuses) for status in TaskStatus),
        )
        self.priority_buttons = self._group_buttons(
            "Priority", "priorityFilters",
            ((priority, priority in priorities) for priority in TaskPriority),
        )
        self.sort_buttons = self._group_buttons(
            "Date", "dateSort", ((True, True), (False, False)),
        )
        self.sort_button_group = QButtonGroup(self)
        self.sort_button_group.setExclusive(True)
        for button in self.sort_buttons.values():
            self.sort_button_group.addButton(button)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        for buttons in (self.status_buttons, self.priority_buttons, self.sort_buttons):
            layout.addWidget(next(iter(buttons.values())).parentWidget())
        if search_widget is not None:

            self.search_group = QGroupBox("Search", self)
            self.search_group.setObjectName("searchFilters")
            search_layout = QHBoxLayout(self.search_group)
            search_layout.setContentsMargins(6, 2, 6, 2)
            search_layout.setSpacing(4)
            search_layout.addWidget(search_widget)
            layout.addWidget(self.search_group, 1)
        else:
            layout.addStretch(1)

    def _group_buttons(
        self,
        title: str,
        name: str,
        entries: Iterable[tuple[FilterKey, bool]],
    ) -> dict[FilterKey, QPushButton]:
        """Build a private button lookup registry for one filter dimension.

        Args:
            title (str): Visible group title.
            name (str): Object name used by the stylesheet.
            entries (Iterable[tuple[FilterKey, bool]]): Filter keys paired with initial checked state.

        Returns:
            dict[FilterKey, QPushButton]: Private widget lookup registry mapping filter keys to buttons.
        """
        group = QGroupBox(title, self)
        group.setObjectName(name)
        layout = QHBoxLayout(group)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)
        buttons = {}
        for key, checked in entries:
            button = QPushButton(group)
            button.setProperty("filterOption", True)
            button.setFixedSize(88, 28)
            button.setCheckable(True)
            button.setChecked(checked)
            buttons[key] = button
            layout.addWidget(button)
        return buttons

