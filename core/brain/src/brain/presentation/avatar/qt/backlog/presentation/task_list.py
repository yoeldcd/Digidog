"""Persistent grouped task rows for the native Qt backlog presentation."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QModelIndex, QSize, Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QWidget

from brain.presentation.avatar.qt.backlog.contracts.models import (
    BacklogThemeTokens,
    TaskPriority,
    TaskStatus,
    TaskView,
    backlog_theme,
)
from brain.presentation.avatar.qt.backlog.presentation.filters import (
    matches_task_search,
    task_date_key,
)
from brain.presentation.avatar.qt.backlog.presentation.widgets import DomainHeader, TaskCard


@dataclass
class _TaskRow:
    """Keep one task item and its stable card widget together.

    Attributes:
        item: Persistent list item carrying the task identity data.
        card: Persistent task card rendered by the list item.
    """

    item: QListWidgetItem
    card: TaskCard


@dataclass
class _DomainRow:
    """Keep one domain item and its stable header widget together.

    Attributes:
        item: Persistent list item reserved for the domain header.
        header: Persistent domain header rendered by the list item.
    """

    item: QListWidgetItem
    header: DomainHeader


class BacklogTaskList(QListWidget):
    """Render a grouped backlog while preserving rows across view transitions."""

    def __init__(
        self,
        theme: BacklogThemeTokens | str = "light",
        statuses: frozenset[TaskStatus] | None = None,
        priorities: frozenset[TaskPriority] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create an empty persistent task list with local visibility controls.

        Args:
            theme: Theme tokens or theme mode used by persistent child widgets.
            statuses: Status values initially visible in the task list.
            priorities: Priority values initially visible in the task list.
            parent: Optional Qt owner for the list widget.
        """
        super().__init__(parent)
        self._theme = backlog_theme(theme) if isinstance(theme, str) else theme
        self._statuses = statuses if statuses is not None else frozenset(TaskStatus)
        self._priorities = priorities if priorities is not None else frozenset(TaskPriority)
        self._query = ""
        self._sort_newest_first = True
        self._tasks_by_id: dict[str, TaskView] = {}
        self._task_rows: dict[str, _TaskRow] = {}
        self._domain_rows: dict[str, _DomainRow] = {}
        self._collapsed_domains: set[str] = set()

    def set_tasks(self, tasks: Sequence[TaskView]) -> None:
        """Reconcile a source snapshot and refresh persistent row visibility.

        Args:
            tasks: Complete task projection snapshot for the selected project.

        Returns:
            None.

        Raises:
            ValueError: If the source snapshot contains duplicate task IDs.
        """
        tasks_by_id = self._index_tasks(tasks)
        if tasks_by_id == self._tasks_by_id:
            return

        self._remove_stale_task_rows(tasks_by_id)
        self._update_existing_task_rows(tasks_by_id)
        self._add_new_task_rows(tasks_by_id)
        self._reconcile_domain_rows(tasks_by_id)
        self._tasks_by_id = tasks_by_id
        self._apply_view()

    def set_query(self, query: str) -> None:
        """Apply a local search query without rebuilding list items.

        Args:
            query: Raw text entered in the task search control.

        Returns:
            None.
        """
        normalized_query = query.strip().casefold()
        if normalized_query == self._query:
            return

        self._query = normalized_query
        self._apply_view()

    def set_filters(
        self,
        statuses: frozenset[TaskStatus],
        priorities: frozenset[TaskPriority],
    ) -> None:
        """Apply local status and priority visibility without rebuilding rows.

        Args:
            statuses: Status values that remain visible.
            priorities: Priority values that remain visible.

        Returns:
            None.
        """
        if statuses == self._statuses and priorities == self._priorities:
            return

        self._statuses = statuses
        self._priorities = priorities
        self._apply_view()

    def set_sort_newest_first(self, newest_first: bool) -> None:
        """Reorder existing list handles using the current date sort direction.

        Args:
            newest_first: Whether newer task dates should appear before older dates.

        Returns:
            None.
        """
        if newest_first == self._sort_newest_first:
            return

        self._sort_newest_first = newest_first
        self._apply_view()

    def set_theme(self, theme: BacklogThemeTokens | str) -> None:
        """Apply theme tokens to all cached headers and cards.

        Args:
            theme: Theme tokens or theme mode applied to persistent child widgets.

        Returns:
            None.
        """
        tokens = backlog_theme(theme) if isinstance(theme, str) else theme
        if tokens == self._theme:
            return

        self._theme = tokens
        for row in self._task_rows.values():
            row.card.apply_theme(tokens)
        for row in self._domain_rows.values():
            row.header.apply_theme(tokens)


    def _index_tasks(self, tasks: Sequence[TaskView]) -> dict[str, TaskView]:
        """Index one source snapshot by the stable task identity.

        Args:
            tasks: Source task projections received from the owning window.

        Returns:
            dict[str, TaskView]: Stable task-ID index for reconciliation.

        Raises:
            ValueError: If two source rows use the same task ID.
        """
        tasks_by_id: dict[str, TaskView] = {}
        for task in tasks:
            if task.task_id in tasks_by_id:
                raise ValueError(f"Duplicate task ID in backlog snapshot: {task.task_id}")
            tasks_by_id[task.task_id] = task

        return tasks_by_id

    def _remove_stale_task_rows(self, tasks_by_id: dict[str, TaskView]) -> None:
        """Remove rows whose task IDs disappeared from the source snapshot.

        Args:
            tasks_by_id: New source snapshot indexed by task ID.
        """
        stale_ids = set(self._task_rows).difference(tasks_by_id)
        for task_id in stale_ids:
            row = self._task_rows.pop(task_id)
            self._remove_row(row.item, row.card)

    def _update_existing_task_rows(self, tasks_by_id: dict[str, TaskView]) -> None:
        """Update changed projections while preserving their row widgets.

        Args:
            tasks_by_id: New source snapshot indexed by task ID.
        """
        for task_id, task in tasks_by_id.items():
            row = self._task_rows.get(task_id)
            if row is None or row.card.task == task:
                continue

            row.item.setData(Qt.ItemDataRole.UserRole, task)
            row.card.update_task(task)

    def _add_new_task_rows(self, tasks_by_id: dict[str, TaskView]) -> None:
        """Create rows only for task IDs absent from the cached source snapshot.

        Args:
            tasks_by_id: New source snapshot indexed by task ID.
        """
        new_ids = set(tasks_by_id).difference(self._task_rows)
        for task_id in new_ids:
            task = tasks_by_id[task_id]
            row = self._create_task_row(task)
            self._task_rows[task_id] = row

    def _reconcile_domain_rows(self, tasks_by_id: dict[str, TaskView]) -> None:
        """Reconcile cached domain headers for the new source snapshot.

        Args:
            tasks_by_id: New source snapshot indexed by task ID.
        """
        domains = {self._domain_for(task) for task in tasks_by_id.values()}
        stale_domains = set(self._domain_rows).difference(domains)
        for domain in stale_domains:
            row = self._domain_rows.pop(domain)
            self._remove_row(row.item, row.header)

        new_domains = domains.difference(self._domain_rows)
        for domain in new_domains:
            row = self._create_domain_row(domain)
            self._domain_rows[domain] = row

    def _create_task_row(self, task: TaskView) -> _TaskRow:
        """Create and append one task item and its card widget.

        Args:
            task: Task projection rendered by the new row.

        Returns:
            _TaskRow: Newly created persistent item and card pair.
        """
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, task)
        card = TaskCard(task, self._theme, self)
        item.setSizeHint(QSize(max(300, card.sizeHint().width()), TaskCard.ROW_HEIGHT))
        self.addItem(item)
        self.setItemWidget(item, card)
        return _TaskRow(item=item, card=card)

    def _create_domain_row(self, domain: str) -> _DomainRow:
        """Create and append one domain item and its header widget.

        Args:
            domain: Normalized domain label displayed by the header.

        Returns:
            _DomainRow: Newly created persistent item and header pair.
        """
        item = QListWidgetItem()
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        is_expanded = domain not in self._collapsed_domains
        header = DomainHeader(domain, 0, self._theme, self, expanded=is_expanded)
        header.toggled.connect(self._on_domain_toggled)
        item.setSizeHint(QSize(max(300, header.sizeHint().width()), header.height()))
        self.addItem(item)
        self.setItemWidget(item, header)
        return _DomainRow(item=item, header=header)

    def _on_domain_toggled(self, domain: str, expanded: bool) -> None:
        """Handle collapse/expand toggle events for a domain group.

        Args:
            domain: Domain identifier toggled.
            expanded: True if domain items should be expanded.
        """
        if expanded:
            self._collapsed_domains.discard(domain)
        else:
            self._collapsed_domains.add(domain)
        self._apply_view()

    def _remove_row(self, item: QListWidgetItem, widget: QWidget) -> None:
        """Remove one reconciled item and schedule its widget for deletion.

        Args:
            item: List item being removed from the persistent view.
            widget: Child widget attached to the removed item.
        """
        row_index = self.row(item)
        if row_index >= 0:
            self.removeItemWidget(item)
            removed_item = self.takeItem(row_index)
            del removed_item

        widget.deleteLater()

    def _apply_view(self) -> None:
        """Apply visibility, header counts, and ordering to cached rows."""
        ordered_items = self._ordered_items()
        self._reorder_items(ordered_items)
        visible_counts = self._visible_task_counts()

        for task_id, row in self._task_rows.items():
            task = self._tasks_by_id[task_id]
            domain = self._domain_for(task)
            is_collapsed = domain in self._collapsed_domains
            row.item.setHidden(is_collapsed or not self._task_is_visible(task))

        for domain, row in self._domain_rows.items():
            visible_count = visible_counts.get(domain, 0)
            row.header.set_task_count(visible_count)
            row.header.set_expanded(domain not in self._collapsed_domains, notify=False)
            row.item.setHidden(visible_count == 0)

    def _ordered_items(self) -> list[QListWidgetItem]:
        """Return cached item handles in grouped date-sort order.

        Returns:
            list[QListWidgetItem]: Existing header and task item handles in display order.
        """
        grouped_tasks: dict[str, list[_TaskRow]] = {}
        for task_id, task in self._tasks_by_id.items():
            domain = self._domain_for(task)
            grouped_tasks.setdefault(domain, []).append(self._task_rows[task_id])

        for rows in grouped_tasks.values():
            rows.sort(key=lambda row: task_date_key(row.card.task), reverse=self._sort_newest_first)

        ordered_items: list[QListWidgetItem] = []
        for domain in sorted(grouped_tasks, key=str.casefold):
            ordered_items.append(self._domain_rows[domain].item)
            ordered_items.extend(row.item for row in grouped_tasks[domain])

        return ordered_items

    def _reorder_items(self, ordered_items: list[QListWidgetItem]) -> None:
        """Move existing model rows into the requested order without recreation.

        Args:
            ordered_items: Existing item handles in their desired display order.
        """
        model = self.model()
        for target_row, item in enumerate(ordered_items):
            current_row = self.row(item)
            if current_row == target_row:
                continue

            destination_row = target_row if current_row > target_row else target_row + 1
            moved = model.moveRow(
                QModelIndex(),
                current_row,
                QModelIndex(),
                destination_row,
            )
            if not moved:
                raise RuntimeError("Unable to preserve backlog row order")

    def _visible_task_counts(self) -> dict[str, int]:
        """Count visible tasks for each normalized domain.

        Returns:
            dict[str, int]: Number of visible task rows grouped by domain.
        """
        visible_counts: dict[str, int] = {}
        for task in self._tasks_by_id.values():
            if not self._task_is_visible(task):
                continue

            domain = self._domain_for(task)
            visible_counts[domain] = visible_counts.get(domain, 0) + 1

        return visible_counts

    def _task_is_visible(self, task: TaskView) -> bool:
        """Return whether one task matches all local visibility controls.

        Args:
            task: Task projection evaluated against the current local view state.

        Returns:
            bool: Whether the task should remain visible.
        """
        if task.status not in self._statuses:
            return False

        priority_values = {priority.value.casefold() for priority in self._priorities}
        if str(task.priority).casefold() not in priority_values:
            return False

        return matches_task_search(task, self._query)

    @staticmethod
    def _domain_for(task: TaskView) -> str:
        """Return the visible grouping label for one task.

        Args:
            task: Task projection whose domain is normalized.

        Returns:
            str: Task domain or the fallback uncategorized label.
        """
        return task.domain or "Uncategorized"