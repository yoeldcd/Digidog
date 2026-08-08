"""Stable-row regression contracts for the native Qt backlog task list."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QListWidgetItem

from brain.presentation.avatar.qt.backlog.contracts.models import (
    TaskPriority,
    TaskStatus,
    TaskView,
)
from brain.presentation.avatar.qt.backlog.presentation.task_list import BacklogTaskList
from brain.presentation.avatar.qt.backlog.presentation.widgets import DomainHeader, TaskCard


def _app() -> QApplication:
    """Return the shared offscreen Qt application used by the widget tests.

    Returns:
        QApplication: Existing application instance or a newly created one.
    """
    return QApplication.instance() or QApplication([])


def _task(
    task_id: str,
    domain: str,
    title: str,
    priority: str,
    status: TaskStatus,
    created_at: float,
) -> TaskView:
    """Build one immutable task projection for a stable-row scenario.

    Args:
        task_id: Stable task identity.
        domain: Grouping domain rendered by the list.
        title: Display title.
        priority: Serialized priority label.
        status: Lifecycle state.
        created_at: Timestamp used by the date sort.

    Returns:
        TaskView: Task projection consumed by the native list.
    """
    return TaskView(
        task_id,
        "alpha",
        domain,
        title,
        "Details",
        priority,
        status,
        created_at,
    )


def _task_handles(task_list: BacklogTaskList) -> dict[str, QListWidgetItem]:
    """Return native list item handles indexed by task ID.

    Args:
        task_list: List whose native items are inspected.

    Returns:
        dict[str, QListWidgetItem]: Task item handles, excluding domain headers.
    """
    handles: dict[str, QListWidgetItem] = {}
    for index in range(task_list.count()):
        item = task_list.item(index)
        task = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(task, TaskView):
            handles[task.task_id] = item

    return handles


def _card(task_list: BacklogTaskList, task_id: str) -> TaskCard:
    """Return the persistent card widget for one task identity.

    Args:
        task_list: List containing the task row.
        task_id: Stable task identity used to locate the row.

    Returns:
        TaskCard: Card attached to the matching native list item.
    """
    item = _task_handles(task_list)[task_id]
    card = task_list.itemWidget(item)
    assert isinstance(card, TaskCard)
    return card


def _domain_row(task_list: BacklogTaskList, domain: str) -> QListWidgetItem:
    """Return the native header item for one domain.

    Args:
        task_list: List containing the domain row.
        domain: Header domain label.

    Returns:
        QListWidgetItem: Native item carrying the domain header widget.
    """
    for index in range(task_list.count()):
        item = task_list.item(index)
        header = task_list.itemWidget(item)
        if isinstance(header, DomainHeader) and header.domain == domain:
            return item

    raise AssertionError(f"Missing domain row: {domain}")


def test_local_view_changes_preserve_native_item_and_widget_identity() -> None:
    """Keep all cached rows stable while query and filters only change visibility."""
    _app()
    task_list = BacklogTaskList()
    tasks = (
        _task("t1", "ui.avatar", "First", "HIGH", TaskStatus.TODO, 100.0),
        _task("t2", "ui.avatar", "Newest", "LOW", TaskStatus.WORKING, 300.0),
        _task("t3", "core.voice", "Done", "MEDIUM", TaskStatus.DONE, 200.0),
    )
    task_list.set_tasks(tasks)
    item_handles = _task_handles(task_list)
    card_handles = {task_id: _card(task_list, task_id) for task_id in item_handles}
    stable_count = task_list.count()

    task_list.set_query("newest")
    task_list.set_filters(
        frozenset({TaskStatus.TODO, TaskStatus.WORKING}),
        frozenset(TaskPriority),
    )
    task_list.set_filters(
        frozenset({TaskStatus.TODO, TaskStatus.WORKING}),
        frozenset({TaskPriority.HIGH}),
    )

    assert task_list.count() == stable_count
    assert _task_handles(task_list) == item_handles
    assert {
        task_id: _card(task_list, task_id) for task_id in item_handles
    } == card_handles
    assert item_handles["t1"].isHidden()
    assert item_handles["t2"].isHidden()
    assert item_handles["t3"].isHidden()

    task_list.set_query("")
    task_list.set_filters(frozenset(TaskStatus), frozenset(TaskPriority))

    assert task_list.count() == stable_count
    assert all(not item.isHidden() for item in item_handles.values())
    assert _task_handles(task_list) == item_handles
    assert {
        task_id: _card(task_list, task_id) for task_id in item_handles
    } == card_handles


def test_date_sort_moves_existing_handles_without_replacement() -> None:
    """Move rows for date sorting while retaining every item and card instance."""
    _app()
    task_list = BacklogTaskList()
    task_list.set_tasks(
        (
            _task("older", "ui.avatar", "Older", "HIGH", TaskStatus.TODO, 100.0),
            _task("newer", "ui.avatar", "Newer", "HIGH", TaskStatus.TODO, 300.0),
        ),
    )
    initial_items = _task_handles(task_list)
    initial_cards = {task_id: _card(task_list, task_id) for task_id in initial_items}

    def visible_task_ids() -> list[str]:
        return [
            task_list.item(index).data(Qt.ItemDataRole.UserRole).task_id
            for index in range(task_list.count())
            if isinstance(task_list.item(index).data(Qt.ItemDataRole.UserRole), TaskView)
            and not task_list.item(index).isHidden()
        ]

    assert visible_task_ids() == ["newer", "older"]
    task_list.set_sort_newest_first(False)

    assert visible_task_ids() == ["older", "newer"]
    assert _task_handles(task_list) == initial_items
    assert {
        task_id: _card(task_list, task_id) for task_id in initial_items
    } == initial_cards


def test_same_task_id_updates_existing_card_and_domain_counts() -> None:
    """Update one stable task card and keep domain visibility tied to visible rows."""
    _app()
    task_list = BacklogTaskList()
    tasks = (
        _task("t1", "ui.avatar", "First", "HIGH", TaskStatus.TODO, 100.0),
        _task("t2", "ui.avatar", "Second", "LOW", TaskStatus.WORKING, 200.0),
        _task("t3", "core.voice", "Done", "MEDIUM", TaskStatus.DONE, 300.0),
    )
    task_list.set_tasks(tasks)
    t1_item = _task_handles(task_list)["t1"]
    t1_card = _card(task_list, "t1")
    ui_header_item = _domain_row(task_list, "ui.avatar")
    core_header_item = _domain_row(task_list, "core.voice")
    ui_header = task_list.itemWidget(ui_header_item)
    core_header = task_list.itemWidget(core_header_item)
    assert isinstance(ui_header, DomainHeader)
    assert isinstance(core_header, DomainHeader)
    assert ui_header.task_count_label.text() == "2"
    assert core_header.task_count_label.text() == "1"

    task_list.set_filters(
        frozenset({TaskStatus.TODO}),
        frozenset({TaskPriority.HIGH}),
    )

    assert ui_header.task_count_label.text() == "1"
    assert core_header.task_count_label.text() == "0"
    assert not ui_header_item.isHidden()
    assert core_header_item.isHidden()
    assert task_list._task_rows["t2"].item.isHidden()
    assert task_list._task_rows["t3"].item.isHidden()

    updated = _task(
        "t1",
        "ui.avatar",
        "Renamed",
        "HIGH",
        TaskStatus.WORKING,
        400.0,
    )
    task_list.set_tasks((updated, *tasks[1:]))

    assert task_list.count() == 5
    assert _task_handles(task_list)["t1"] is t1_item
    assert _card(task_list, "t1") is t1_card
    assert t1_card.task == updated
    assert t1_card.title_label.text() == "Renamed"
