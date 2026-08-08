"""Focused contracts for the standalone Qt backlog task manager."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect, QSize, Qt, QUrl
from PySide6.QtGui import QColor, QImage, QPixmap, QTextBlock, QTextDocument, QTextImageFormat
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCompleter, QWidget

from brain.presentation.avatar.qt.backlog.annotation import (
    ANNOTATION_PALETTE,
    AnnotationCanvas,
    AnnotationDialog,
)
from brain.presentation.avatar.qt.backlog import presentation as backlog_presentation
from brain.presentation.avatar.qt.backlog.presentation.capture import QtScreenCapture
from brain.application.backlog.models import BacklogTask
from brain.presentation.avatar.qt.backlog.application.composition import (
    _matching_project_key,
    _task_view,
)
from brain.presentation.avatar.qt.backlog.application.controller import BacklogController
from brain.presentation.avatar.qt.backlog.presentation.detail import TaskDetailPanel
from brain.presentation.avatar.qt.backlog.presentation.form import TaskFormDialog
from brain.presentation.avatar.qt.backlog.presentation.icons import STATUS_ICON_NAMES, SVG_PATHS
from brain.presentation.avatar.qt.backlog.contracts.models import (
    EditTaskDraft,
    NewTaskDraft,
    ProjectView,
    TaskEditSource,
    TaskPriority,
    TaskStatus,
    TaskView,
    backlog_theme,
)
from brain.presentation.avatar.qt.backlog.presentation.widgets import DomainHeader, TaskCard
from brain.presentation.avatar.qt.backlog.presentation.window import BacklogWindow
from brain.presentation.avatar.qt.markdown.document import AvatarTextBrowser


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _task(task_id: str, project: str = "alpha", status: TaskStatus = TaskStatus.TODO) -> TaskView:
    return TaskView(task_id, project, "ui.avatar", f"Task {task_id}", "Details", "HIGH", status)


def _all_task_items(window: BacklogWindow) -> list:
    """Return every native task item, including hidden rows."""
    return [
        window.task_list.item(index)
        for index in range(window.task_list.count())
        if isinstance(window.task_list.item(index).data(Qt.ItemDataRole.UserRole), TaskView)
    ]


def _task_items(window: BacklogWindow) -> list:
    """Return only currently visible native task items."""
    return [item for item in _all_task_items(window) if not item.isHidden()]


def test_matches_task_search_uses_title_only_case_insensitively() -> None:
    """Search matches title text but ignores every other task field."""
    task = TaskView(
        "task-id-needle",
        "alpha",
        "domain-needle",
        "Visible Title",
        "description-needle",
        "HIGH",
        TaskStatus.WORKING,
    )

    assert backlog_presentation.matches_task_search(task, "visible title")
    assert backlog_presentation.matches_task_search(task, "VISIBLE")
    for query in ("task-id-needle", "domain-needle", "description-needle", "high", "working"):
        assert not backlog_presentation.matches_task_search(task, query)


def _document_image_format(document: QTextDocument) -> tuple[QTextBlock, QTextImageFormat]:
    """Return the first embedded image format and containing document block.

    Args:
        document: Qt rich-text document rendered by the task detail panel.

    Returns:
        tuple[QTextBlock, QTextImageFormat]: Containing block and its valid image format.

    Raises:
        AssertionError: If the rendered document does not contain an image.
    """
    block = document.begin()

    while block.isValid():
        iterator = block.begin()

        while not iterator.atEnd():
            image_format = iterator.fragment().charFormat().toImageFormat()
            if image_format.isValid():
                return block, image_format

            iterator += 1

        block = block.next()

    raise AssertionError("Expected one rendered document image.")


def _reader_fitted_image_size(intrinsic: QSize, bounds: QSize) -> QSize:
    """Return the aspect-fit size of an unrequested detail image.

    Args:
        intrinsic: Natural source image dimensions.
        bounds: Actual usable detail-reader image bounds.

    Returns:
        QSize: Aspect-preserving size limited by the reader bounds.
    """
    scale = min(bounds.width() / intrinsic.width(), bounds.height() / intrinsic.height())

    return QSize(round(intrinsic.width() * scale), round(intrinsic.height() * scale))


def test_workspace_match_is_case_insensitive_on_windows() -> None:
    root = os.path.abspath(".")
    project = ProjectView(root, "Current")
    assert _matching_project_key(root.swapcase(), (project,)) == root


def test_controller_defaults_filters_and_switches_projects() -> None:
    calls: list[tuple[str, frozenset[TaskStatus] | None]] = []
    controller = BacklogController(
        lambda: [ProjectView("alpha", "Alpha"), ProjectView("beta", "Beta")],
        lambda project, statuses: calls.append((project, statuses)) or [_task("t1", project)],
        lambda draft: _task("t2", draft.project),
    )
    controller.initialize()
    assert controller.selected_project == "alpha"
    assert controller.statuses == frozenset({TaskStatus.TODO, TaskStatus.WORKING})
    assert calls == [
        ("alpha", frozenset(TaskStatus)),
        ("alpha", None),
    ]
    controller.set_statuses(frozenset({TaskStatus.DONE}))
    assert calls == [
        ("alpha", frozenset(TaskStatus)),
        ("alpha", None),
    ]
    controller.select_project("beta")
    assert calls == [
        ("alpha", frozenset(TaskStatus)),
        ("alpha", None),
        ("beta", frozenset(TaskStatus)),
        ("beta", None),
    ]


def test_window_lifecycle_filter_selection_cancel_and_submission() -> None:
    _app()
    drafts: list[NewTaskDraft] = []
    tasks = [_task("t1")]

    def create(draft: NewTaskDraft) -> TaskView:
        drafts.append(draft)
        created = _task("t2", draft.project)
        tasks.append(created)
        return created

    controller = BacklogController(lambda: [ProjectView("alpha", "Alpha")],
        lambda project, statuses: list(tasks), create)
    window = BacklogWindow(controller)
    assert len(_task_items(window)) == 1
    assert not window.status_buttons[TaskStatus.DONE].isChecked()
    window.status_buttons[TaskStatus.TODO].setChecked(False)
    assert window.task_list.count() == 2
    assert len(_task_items(window)) == 0
    assert len(_all_task_items(window)) == 1
    window.add_button.click()
    form = window._task_form
    assert isinstance(form, TaskFormDialog)
    assert form.parent() is None
    form.domain_input.setText("ui.avatar")
    form.title_input.setText("New task")
    form.reject()
    assert window._task_form is None
    window.add_button.click()
    form = window._task_form
    assert isinstance(form, TaskFormDialog)
    form.domain_input.setText("ui.avatar")
    form.title_input.setText("New task")
    form.submit_task()
    assert drafts[0].title == "New task"
    assert window._task_form is None
    window.close()


def test_controller_priority_filter_and_project_domain_suggestions() -> None:
    tasks = {
        "alpha": [
            TaskView("t1", "alpha", "ui.avatar", "High", "Details", "HIGH", TaskStatus.TODO),
            TaskView("t2", "alpha", "core.voice", "Low", "Details", "LOW", TaskStatus.WORKING),
        ],
        "beta": [
            TaskView(
                "t3",
                "beta",
                "api.http",
                "Medium",
                "Details",
                "MEDIUM",
                TaskStatus.TODO,
            ),
        ],
    }
    controller = BacklogController(
        lambda: [ProjectView("alpha", "Alpha"), ProjectView("beta", "Beta")],
        lambda project, statuses: list(tasks[project]),
        lambda draft: tasks[draft.project][0],
    )
    controller.initialize()
    assert controller.domain_suggestions == ("core.voice", "ui.avatar")
    assert [task.task_id for task in controller.set_priorities(frozenset({TaskPriority.LOW}))] == [
        "t1",
        "t2",
    ]
    controller.select_project("beta")
    assert controller.domain_suggestions == ("api.http",)


def test_window_theme_cards_filters_icons_suggestions_and_markdown_detail() -> None:
    app = _app()
    task = TaskView(
        "t1",
        "alpha",
        "ui.avatar",
        "Rich task",
        "**Rendered detail**",
        "HIGH",
        TaskStatus.TODO,
    )
    controller = BacklogController(
        lambda: [ProjectView("alpha", "Alpha")],
        lambda project, statuses: [task],
        lambda draft: task,
    )
    window = BacklogWindow(controller, theme="dark")
    assert window.theme_tokens.mode == "dark"
    assert window.property("avatarTheme") == "dark"
    assert not window.refresh_button.icon().isNull()
    assert not window.add_button.icon().isNull()
    assert set(window.priority_buttons) == set(TaskPriority)
    assert window.findChild(QWidget, "statusFilters") is not None
    assert window.findChild(QWidget, "priorityFilters") is not None
    task_item = _task_items(window)[0]
    card = window.task_list.itemWidget(task_item)
    assert isinstance(card, TaskCard)
    assert card.height() == TaskCard.ROW_HEIGHT == 40
    assert task_item.sizeHint().height() == 40
    assert not card.status_icon.pixmap().isNull()
    assert not card.chevron.pixmap().isNull()
    assert "ui.avatar" in card.accessibleName()
    window.add_button.click()
    form = window._task_form
    assert isinstance(form, TaskFormDialog)
    assert [form.domain_input.itemText(index) for index in range(form.domain_input.count())] == [
        "ui.avatar",
    ]
    assert form.priority_selector.maximumWidth() == 132
    assert form.capture_button.text() == "Capture"
    form._capture_pixmap = QPixmap(8, 8)
    form._sync_capture_state()
    assert form.capture_button.text() == "Edit annotations"
    stylesheet = window.styleSheet()
    assert "QComboBox::drop-down" in stylesheet
    assert window.theme_tokens.surface in stylesheet
    assert window.theme_tokens.selected in stylesheet
    assert "border: 2px solid" in stylesheet
    popup_style = form.priority_selector.view().styleSheet()
    assert window.theme_tokens.text in popup_style
    assert window.theme_tokens.surface in popup_style
    assert window.theme_tokens.accent in popup_style
    completer_popup_style = form.domain_input.completer().popup().styleSheet()
    assert window.theme_tokens.text in completer_popup_style
    assert window.theme_tokens.surface in completer_popup_style
    assert window.theme_tokens.accent in completer_popup_style
    form.reject()
    headers = [
        window.task_list.itemWidget(window.task_list.item(index))
        for index in range(window.task_list.count())
        if isinstance(window.task_list.itemWidget(window.task_list.item(index)), DomainHeader)
    ]
    assert [header.domain for header in headers] == ["ui.avatar"]
    window.show_task_detail(task_item)
    app.processEvents()
    assert isinstance(window.detail_panel, TaskDetailPanel)
    assert isinstance(window.detail_panel.document_view, AvatarTextBrowser)
    assert window.page_stack.currentWidget() is window.detail_panel
    assert window.list_page.isHidden()
    assert not hasattr(window, "detail_bubble")
    detail_text = window.detail_panel.document_view.toPlainText()
    assert "Rich task" not in detail_text
    assert "Rendered detail" in detail_text
    window.detail_panel.back_button.click()
    assert window.page_stack.currentWidget() is window.list_page
    assert window.detail_panel.isHidden()
    window.close()


def test_task_detail_uses_native_badges_elided_header_equal_actions_and_bordered_images(tmp_path) -> None:
    """Qt renders task references with non-duplicated native metadata."""
    app = _app()
    pictures_dir = tmp_path / "$agent" / "pictures"
    pictures_dir.mkdir(parents=True)
    image_path = pictures_dir / "backlog-pic-t715.png"
    image = QImage(24, 12, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    assert image.save(str(image_path))
    persistent_task = BacklogTask(
        task_id="t715",
        domain="ui.avatar.detail",
        title="Long title " * 32,
        description="Task reference follows.\n\n{ref_image}",
        priority="HIGH",
        status="TODO",
    )
    task = _task_view(str(tmp_path), persistent_task)
    assert persistent_task.description.endswith("{ref_image}")
    assert "![Task reference]($agent/pictures/backlog-pic-t715.png)" in task.description

    panel = TaskDetailPanel()
    assert isinstance(panel.document_view, backlog_presentation.TaskDetailDocumentView)
    assert isinstance(panel.metadata_bar, backlog_presentation.TaskMetadataBar)
    assert all(
        isinstance(badge, backlog_presentation.TaskMetadataBadge)
        for badge in panel.metadata_bar.badges
    )
    theme = backlog_theme("dark")
    panel.set_theme(theme)
    panel.set_task(task)
    panel.resize(760, 440)
    panel.show()
    app.processEvents()

    identity = f"{task.task_id} - {task.title}"
    detail_text = panel.document_view.toPlainText()
    metadata = panel.metadata_bar
    available_domain_width = metadata.width() - metadata.status_badge.width() - metadata.priority_badge.width() - 12
    assert panel.heading.toolTip() == identity
    assert panel.heading.accessibleName() == identity
    assert panel.heading.text() != identity
    assert task.title not in detail_text
    assert "Field" not in detail_text
    assert "{ref_image}" not in detail_text
    assert len(metadata.badges) == 3
    assert not hasattr(metadata, "task_id_badge")
    assert all("t715" not in badge.accessibleName() for badge in metadata.badges)
    assert all(badge.accessibleName() and badge.icon_label.pixmap() is not None for badge in metadata.badges)
    assert metadata.status_badge.width() == metadata.priority_badge.width()
    assert metadata.status_badge.width() >= metadata.status_badge.natural_width()
    assert metadata.priority_badge.width() >= metadata.priority_badge.natural_width()
    assert metadata.domain_badge.width() == available_domain_width
    assert len({button.width() for button in panel._action_buttons}) == 1
    assert panel.start_button.isEnabled() and panel.done_button.isEnabled()

    block, image_format = _document_image_format(panel.document_view.document())
    assert block.blockFormat().alignment() == Qt.AlignmentFlag.AlignCenter
    displayed_size = QSize(round(image_format.width()), round(image_format.height()))
    image_bounds = panel._image_viewport_size()
    assert displayed_size.width() > image.width() or displayed_size.height() > image.height()
    assert displayed_size.width() / displayed_size.height() == pytest.approx(2.0, rel=0.05)
    assert displayed_size.width() <= image_bounds.width()
    assert displayed_size.height() <= image_bounds.height()
    resource = panel.document_view.document().resource(
        QTextDocument.ResourceType.ImageResource,
        QUrl(image_format.name()),
    )
    assert isinstance(resource, QImage)
    assert resource.size() == image.size()
    assert resource.pixelColor(1, 1) == QColor(theme.accent)
    assert resource.pixelColor(resource.width() - 2, resource.height() - 2) == QColor(theme.accent)

    long_domain = "ui.avatar." + ("detail." * 80)
    long_task = TaskView(
        task.task_id,
        task.project,
        long_domain,
        task.title,
        task.description,
        task.priority,
        task.status,
    )
    panel.set_task(long_task)
    app.processEvents()
    capped_domain_width = metadata.width() - metadata.status_badge.width() - metadata.priority_badge.width() - 12
    assert metadata.domain_badge.width() == capped_domain_width
    assert metadata.domain_badge.text_label.text() != long_domain
    assert metadata.domain_badge.toolTip() == f"Domain: {long_domain}"
    assert metadata.domain_badge.accessibleName() == f"Domain: {long_domain}"
    explicit_task = TaskView(
        task.task_id,
        task.project,
        task.domain,
        task.title,
        f'<img src="{image_path.as_uri()}" width="48" height="24">',
        task.priority,
        task.status,
    )
    panel.set_task(explicit_task)
    app.processEvents()
    explicit_block = panel.document_view.document().begin()
    explicit_format = explicit_block.begin().fragment().charFormat().toImageFormat()
    assert explicit_format.isValid()
    assert QSize(round(explicit_format.width()), round(explicit_format.height())) == QSize(48, 24)
    panel.close()


def test_task_detail_reflows_reference_images_after_hidden_stack_activation(tmp_path) -> None:
    """Qt reflows a task reference after QStackedWidget makes detail visible."""
    app = _app()
    pictures_dir = tmp_path / "$agent" / "pictures"
    pictures_dir.mkdir(parents=True)
    image_path = pictures_dir / "backlog-pic-t715-hidden.png"
    image = QImage(24, 12, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    assert image.save(str(image_path))
    persistent_task = BacklogTask(
        task_id="t715-hidden",
        domain="ui.avatar.detail",
        title="Hidden detail reference",
        description="Reference from task storage.\n\n{ref_image}",
        priority="HIGH",
        status="TODO",
    )
    task = _task_view(str(tmp_path), persistent_task)
    assert "![Task reference]($agent/pictures/backlog-pic-t715-hidden.png)" in task.description
    controller = BacklogController(
        lambda: [ProjectView(str(tmp_path), "Temporary")],
        lambda project, statuses: [task],
        lambda draft: task,
    )
    window = BacklogWindow(controller, theme="dark")
    task_item = _task_items(window)[0]
    assert window.page_stack.currentWidget() is window.list_page
    assert window.detail_panel.isHidden()

    window.resize(940, 680)
    window.show()
    app.processEvents()
    window.show_task_detail(task_item)
    app.processEvents()
    QTest.qWait(20)

    assert window.page_stack.currentWidget() is window.detail_panel
    assert window.detail_panel.isVisible()
    block, image_format = _document_image_format(window.detail_panel.document_view.document())
    initial_size = QSize(round(image_format.width()), round(image_format.height()))
    initial_bounds = window.detail_panel._image_viewport_size()
    assert initial_size == _reader_fitted_image_size(image.size(), initial_bounds)
    assert initial_size.width() > image.width()
    assert initial_size.height() > image.height()
    assert block.blockFormat().alignment() == Qt.AlignmentFlag.AlignCenter
    resource = window.detail_panel.document_view.document().resource(
        QTextDocument.ResourceType.ImageResource,
        QUrl(image_format.name()),
    )
    assert isinstance(resource, QImage)
    assert resource.size() == image.size()
    assert resource.pixelColor(1, 1) == QColor(window.theme_tokens.accent)
    assert resource.pixelColor(resource.width() - 2, resource.height() - 2) == QColor(window.theme_tokens.accent)

    window.resize(760, 520)
    app.processEvents()
    QTest.qWait(20)

    resized_block, resized_format = _document_image_format(window.detail_panel.document_view.document())
    resized_size = QSize(round(resized_format.width()), round(resized_format.height()))
    resized_bounds = window.detail_panel._image_viewport_size()
    assert resized_size == _reader_fitted_image_size(image.size(), resized_bounds)
    assert resized_size != initial_size
    assert resized_block.blockFormat().alignment() == Qt.AlignmentFlag.AlignCenter
    window.close()


def test_tasks_are_compactly_grouped_by_domain() -> None:
    _app()
    tasks = [
        TaskView("t1", "alpha", "ui.avatar", "First", "Details", "HIGH", TaskStatus.TODO),
        TaskView("t2", "alpha", "core.voice", "Second", "Details", "LOW", TaskStatus.WORKING),
        TaskView("t3", "alpha", "ui.avatar", "Third", "Details", "MEDIUM", TaskStatus.TODO),
    ]
    controller = BacklogController(
        lambda: [ProjectView("alpha", "Alpha")],
        lambda project, statuses: list(tasks),
        lambda draft: tasks[0],
    )
    window = BacklogWindow(controller)
    widgets = [
        window.task_list.itemWidget(window.task_list.item(index))
        for index in range(window.task_list.count())
    ]
    headers = [widget for widget in widgets if isinstance(widget, DomainHeader)]
    rows = [widget for widget in widgets if isinstance(widget, TaskCard)]
    assert [header.domain for header in headers] == ["core.voice", "ui.avatar"]
    assert len(rows) == 3
    assert all(row.height() == 40 for row in rows)
    assert all("border: 1px solid" in row.styleSheet() for row in rows)
    window.close()


def test_modern_action_identity_svg_paths_and_light_contrast() -> None:
    _app()
    controller = BacklogController(
        lambda: [ProjectView("alpha", "Alpha")],
        lambda project, statuses: [_task("t1")],
        lambda draft: _task("t2"),
    )
    window = BacklogWindow(controller, theme="light")
    light = backlog_theme("light")
    assert light.background != "#ffffff"
    assert light.surface != "#ffffff"
    assert light.background == "#e9e1e6"
    assert SVG_PATHS[STATUS_ICON_NAMES["TODO"]] == (
        '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>'
    )
    assert SVG_PATHS[STATUS_ICON_NAMES["WORKING"]] == (
        '<path d="M3 12h4l2-6 4 12 2-6h6"/>'
    )
    assert "<rect" in SVG_PATHS[STATUS_ICON_NAMES["DONE"]]
    assert window.refresh_button.text() == ""
    assert window.refresh_button.toolTip()
    assert window.refresh_button.accessibleName() == "Refresh tasks"
    assert window.add_button.text() == "Add task"
    assert window.add_button.toolTip()
    assert not window.add_button.icon().isNull()
    for button in (*window.status_buttons.values(), *window.priority_buttons.values()):
        assert button.text()
        assert button.toolTip()
        assert button.accessibleName()
        assert not button.icon().isNull()
    window.add_button.click()
    form = window._task_form
    assert isinstance(form, TaskFormDialog)
    for button in (form.capture_button, form.cancel_button, form.submit_button):
        assert button.text()
    assert form.capture_button.toolTip()
    assert form.capture_button.accessibleName()
    assert not form.capture_button.icon().isNull()
    form.reject()
    window.close()


def test_domain_completion_is_hierarchical_popup_only_and_non_mutating() -> None:
    _app()
    controller = BacklogController(
        lambda: [ProjectView("alpha", "Alpha")],
        lambda project, statuses: [
            TaskView("t1", "alpha", "core.voice.tts", "One", "", "HIGH", TaskStatus.TODO),
            TaskView("t2", "alpha", "core.vector", "Two", "", "HIGH", TaskStatus.TODO),
            TaskView("t3", "alpha", "ui.voice", "Three", "", "HIGH", TaskStatus.TODO),
        ],
        lambda draft: _task("t4"),
    )
    window = BacklogWindow(controller)
    window.add_button.click()
    form = window._task_form
    assert isinstance(form, TaskFormDialog)
    combo = form.domain_input
    assert combo.completer().completionMode() == QCompleter.CompletionMode.PopupCompletion
    assert combo.filtered_suggestions("core.v") == ("core.vector", "core.voice.tts")
    assert combo.filtered_suggestions("core.voice.") == ("core.voice.tts",)
    assert combo.filtered_suggestions("voice") == ()
    combo.setText("core.v")
    combo.lineEdit().textEdited.emit("core.v")
    assert combo.currentText() == "core.v"
    assert combo._completion_model.stringList() == ["core.vector", "core.voice.tts"]
    form.reject()
    window.close()


def test_ten_tasks_fit_one_typical_list_viewport() -> None:
    _app()
    tasks = [
        TaskView(f"t{index}", "alpha", "ui.avatar", f"Task {index}", "", "LOW", TaskStatus.TODO)
        for index in range(10)
    ]
    controller = BacklogController(
        lambda: [ProjectView("alpha", "Alpha")],
        lambda project, statuses: list(tasks),
        lambda draft: tasks[0],
    )
    window = BacklogWindow(controller)
    total_height = sum(
        window.task_list.item(index).sizeHint().height()
        for index in range(window.task_list.count())
    )
    assert len(_task_items(window)) == 10
    assert total_height == DomainHeader.HEADER_HEIGHT + 10 * TaskCard.ROW_HEIGHT
    assert total_height <= 424
    window.close()


def test_full_page_create_search_and_real_date_sort_contracts() -> None:
    _app()
    tasks = [
        TaskView("t1", "alpha", "ui.avatar", "Needle", "Details", "HIGH", TaskStatus.TODO, 100.0),
        TaskView("t2", "alpha", "ui.avatar", "Newest", "Needle in details", "LOW", TaskStatus.TODO, 300.0),
        TaskView("t9", "alpha", "ui.avatar", "Legacy", "Details", "MEDIUM", TaskStatus.TODO),
    ]
    controller = BacklogController(
        lambda: [ProjectView("alpha", "Alpha")],
        lambda project, statuses: list(tasks),
        lambda draft: tasks[0],
    )
    window = BacklogWindow(controller)
    assert window.page_stack.currentWidget() is window.list_page
    assert window.project_selector.sizePolicy().horizontalPolicy().name == "Expanding"
    assert window.project_selector.minimumWidth() == 240
    assert window.search_input.sizePolicy().horizontalPolicy().name == "Expanding"
    assert window.search_input.parentWidget() is window.filter_bar.search_group
    assert window.filter_bar.search_group.title() == "Search"
    window.show()
    _app().processEvents()
    date_group = window.sort_buttons[True].parentWidget()
    assert window.filter_bar.search_group.geometry().center().y() == date_group.geometry().center().y()
    assert window.search_input.height() == window.sort_buttons[True].height()
    search_icon_button = next(
        button
        for button in window.search_input.findChildren(QWidget)
        if getattr(button, "defaultAction", lambda: None)() is window.search_action
    )
    assert search_icon_button.geometry().center().y() == window.search_input.rect().center().y()
    assert backlog_theme("dark").accent_text == "#171418"
    assert backlog_theme("light").accent_text == "#ffffff"
    filter_sizes = {button.size().toTuple() for button in (
        *window.status_buttons.values(),
        *window.priority_buttons.values(),
        *window.sort_buttons.values(),
    )}
    assert len(filter_sizes) == 1
    assert [
        window.sort_buttons[value].text()
        for value in (True, False)
    ] == ["Recientes", "Antiguos"]
    assert [
        item.data(Qt.ItemDataRole.UserRole).task_id
        for item in _task_items(window)
    ] == ["t2", "t1", "t9"]

    window.sort_buttons[False].click()
    assert [
        item.data(Qt.ItemDataRole.UserRole).task_id
        for item in _task_items(window)
    ] == ["t9", "t1", "t2"]
    window.search_input.setText("needle")
    assert [item.data(Qt.ItemDataRole.UserRole).task_id for item in _task_items(window)] == ["t1"]

    window.add_button.click()
    form = window._task_form
    assert isinstance(form, TaskFormDialog)
    assert form.isVisible()
    assert form.parent() is None
    form.reject()
    app = _app()
    app.processEvents()
    assert window._task_form is None
    window.close()


def test_task_view_maps_created_at_and_annotation_editor_is_modeless_single_instance() -> None:
    app = _app()
    durable = BacklogTask("t3", "ui.avatar", "Mapped", "", "HIGH", "TODO", created_at=123.5)
    with patch("pathlib.Path.is_file") as is_file:
        projected = _task_view("alpha", durable)

    assert projected.created_at == 123.5
    is_file.assert_not_called()

    class Capture:
        def capture(self) -> QPixmap:
            pixmap = QPixmap(12, 12)
            pixmap.fill(QColor("magenta"))
            return pixmap

    controller = BacklogController(
        lambda: [ProjectView("alpha", "Alpha")],
        lambda project, statuses: [],
        lambda draft: _task("t4"),
    )
    window = BacklogWindow(controller, Capture())
    window.add_button.click()
    form = window._task_form
    assert isinstance(form, TaskFormDialog)
    form.capture_screenshot()
    editor = form._annotation_editor
    assert editor is not None
    assert editor.isVisible()
    form.capture_screenshot()
    assert form._annotation_editor is editor
    editor.accept()
    app.processEvents()
    assert form._annotation_editor is None
    assert not form._capture_pixmap.isNull()
    form.reject()
    window.close()

def test_annotation_geometry_remove_clear_and_baking() -> None:
    _app()
    pixmap = QPixmap(100, 50)
    pixmap.fill(QColor("white"))
    canvas = AnnotationCanvas(pixmap)
    canvas.setMinimumSize(0, 0)
    canvas.resize(200, 100)
    canvas.set_color(ANNOTATION_PALETTE["Red"])
    canvas.add_rectangle(QRect(20, 10, 40, 30))
    canvas.set_color(ANNOTATION_PALETTE["Blue"])
    canvas.add_rectangle(QRect(80, 20, 30, 20))
    assert [mark.color for mark in canvas.marks] == [
        ANNOTATION_PALETTE["Red"],
        ANNOTATION_PALETTE["Blue"],
    ]
    assert canvas.rectangles == (QRect(20, 10, 40, 30), QRect(80, 20, 30, 20))
    baked = canvas.baked_pixmap()
    assert baked.size() == pixmap.size()
    canvas.remove_last()
    assert canvas.rectangles == (QRect(20, 10, 40, 30),)
    canvas.clear_annotations()
    assert canvas.rectangles == ()


def test_annotation_clips_marks_to_aspect_ratio_image_bounds() -> None:
    _app()
    source = QPixmap(200, 50)
    source.fill(QColor("white"))
    canvas = AnnotationCanvas(source)
    canvas.setMinimumSize(0, 0)
    canvas.resize(200, 200)
    image_rect = canvas._image_rect()
    assert image_rect == QRect(0, 75, 200, 50)
    canvas.add_rectangle(QRect(10, 10, 40, 20))
    assert canvas.rectangles == ()
    canvas.add_rectangle(QRect(10, 60, 40, 40))
    assert canvas.rectangles == (QRect(10, 75, 40, 25),)
    assert canvas.baked_pixmap().size() == source.size()


def test_annotation_palette_colors_remain_supported_for_future_marks() -> None:
    _app()
    source = QPixmap(100, 50)
    source.fill(QColor("white"))
    canvas = AnnotationCanvas(source)
    canvas.resize(200, 100)
    canvas.set_color(ANNOTATION_PALETTE["Green"])
    canvas.add_rectangle(QRect(10, 10, 30, 20))
    canvas.set_color(ANNOTATION_PALETTE["Yellow"])
    canvas.add_rectangle(QRect(60, 10, 30, 20))
    assert [mark.color for mark in canvas.marks] == [
        ANNOTATION_PALETTE["Green"],
        ANNOTATION_PALETTE["Yellow"],
    ]


def test_baked_pixmap_preserves_each_annotation_color() -> None:
    _app()
    source = QPixmap(100, 50)
    source.fill(QColor("white"))
    canvas = AnnotationCanvas(source)
    canvas.resize(500, 300)
    canvas.set_color(ANNOTATION_PALETTE["Red"])
    canvas.add_rectangle(QRect(50, 50, 100, 50))
    canvas.set_color(ANNOTATION_PALETTE["Blue"])
    canvas.add_rectangle(QRect(250, 50, 100, 50))
    baked = canvas.baked_pixmap().toImage()
    assert baked.pixelColor(10, 5).red() > baked.pixelColor(10, 5).blue()
    assert baked.pixelColor(50, 5).blue() > baked.pixelColor(50, 5).red()

def test_annotation_dialog_cancel_does_not_mutate_source() -> None:
    _app()
    source = QPixmap(20, 20)
    source.fill(QColor("white"))
    before = source.toImage()
    dialog = AnnotationDialog(source)
    dialog.canvas.add_rectangle(QRect(2, 2, 10, 10))
    dialog.reject()
    assert source.toImage() == before


def test_capture_hides_and_restores_avatar_process_windows() -> None:
    app = _app()
    visible = QWidget()
    visible.show()
    app.processEvents()

    class ObservingScreen:
        def grabWindow(self, window_id: int) -> QPixmap:  # noqa: N802
            assert window_id == 0
            assert not visible.isVisible()
            result = QPixmap(8, 8)
            result.fill(QColor("green"))
            return result

    capture = QtScreenCapture(
        lambda: ObservingScreen(),
        settle_windows=lambda: app.processEvents(),
    )  # type: ignore[arg-type]
    assert not capture.capture().isNull()
    assert visible.isVisible()
    visible.close()


def test_capture_restores_windows_when_settling_fails() -> None:
    app = _app()
    visible = QWidget()
    visible.show()
    app.processEvents()

    def fail_settle() -> None:
        app.processEvents()
        raise RuntimeError("settle failed")

    capture = QtScreenCapture(lambda: None, settle_windows=fail_settle)
    with pytest.raises(RuntimeError, match="settle failed"):
        capture.capture()
    assert visible.isVisible()
    visible.close()


def test_capture_post_restore_settle_runs_after_windows_are_visible() -> None:
    app = _app()
    visible = QWidget()
    visible.show()
    app.processEvents()
    events: list[tuple[str, bool]] = []

    class ObservingScreen:
        def grabWindow(self, window_id: int) -> QPixmap:  # noqa: N802
            del window_id
            events.append(("grab", visible.isVisible()))
            result = QPixmap(8, 8)
            result.fill(QColor("green"))
            return result

    capture = QtScreenCapture(
        lambda: ObservingScreen(),
        settle_windows=lambda: events.append(("pre", visible.isVisible())),
        post_restore_settle=lambda: events.append(("post", visible.isVisible())),
        restore_delay_ms=0,
    )
    assert not capture.capture().isNull()
    assert events == [("pre", False), ("grab", False), ("post", True)]
    assert visible.isVisible()
    visible.close()


def test_capture_restore_delay_is_injected_and_configurable() -> None:
    _app()
    delays: list[int] = []
    capture = QtScreenCapture(
        lambda: None,
        restore_delay_ms=37,
        sleep_ms=delays.append,
    )
    capture._default_post_restore_settle()
    assert delays == [37]


def test_capture_adapter_uses_desktop_window_contract() -> None:
    _app()
    calls: list[int] = []

    class FakeScreen:
        def grabWindow(self, window_id: int) -> QPixmap:  # noqa: N802
            calls.append(window_id)
            result = QPixmap(8, 8)
            result.fill(QColor("blue"))
            return result

    capture = QtScreenCapture(lambda: FakeScreen())  # type: ignore[arg-type]
    assert not capture.capture().isNull()
    assert calls == [0]
    assert QtScreenCapture(lambda: None).capture().isNull()



def test_edit_form_loads_raw_marker_and_existing_reference_for_annotations() -> None:
    """Editing consumes persisted RAW text and initializes the canonical PNG."""
    app = _app()
    task = _task("t1")
    source_pixmap = QPixmap(12, 10)
    source_pixmap.fill(QColor("magenta"))
    reference_png = TaskFormDialog._pixmap_png(source_pixmap)
    assert reference_png is not None

    source = TaskEditSource(
        project=task.project,
        task_id=task.task_id,
        domain=task.domain,
        title=task.title,
        raw_description="Raw evidence\n\n{ref_image}",
        priority=task.priority,
        reference_png=reference_png,
    )
    drafts: list[EditTaskDraft] = []
    controller = BacklogController(
        lambda: [ProjectView("alpha", "Alpha")],
        lambda project, statuses: [task],
        lambda draft: task,
        edit_task=lambda draft: drafts.append(draft) or task,
        load_edit_source=lambda project, task_id: source,
    )
    window = BacklogWindow(controller)

    window._open_edit_form(task)
    form = window._task_form
    assert isinstance(form, TaskFormDialog)
    assert form.description_input.toPlainText() == "Raw evidence\n\n{ref_image}"
    assert not form._capture_pixmap.isNull()
    assert not form.capture_heading.isHidden()
    assert not form.capture_button.isHidden()
    assert not form.capture_label.isHidden()
    assert form.capture_button.isEnabled()
    assert form.capture_button.text() == "Edit annotations"

    form.capture_screenshot()
    editor = form._annotation_editor
    assert isinstance(editor, AnnotationDialog)
    editor.accept()
    app.processEvents()

    form.submit_task()
    assert drafts[0].description == "Raw evidence\n\n{ref_image}"
    assert drafts[0].screenshot_png is not None
    assert drafts[0].screenshot_png.startswith(b"\x89PNG")
    window.close()



def test_edit_form_without_reference_keeps_capture_action_available() -> None:
    """Editing a task without an image can add and annotate a new capture."""
    _app()
    task = _task("t2")
    source = TaskEditSource(
        project=task.project,
        task_id=task.task_id,
        domain=task.domain,
        title=task.title,
        raw_description="Raw without image",
        priority=task.priority,
    )

    class Capture:
        """Deterministic screenshot provider for edit-mode coverage."""

        def capture(self) -> QPixmap:
            """Return a non-null image available for annotation."""
            pixmap = QPixmap(10, 10)
            pixmap.fill(QColor("cyan"))
            return pixmap

    form = TaskFormDialog(edit_source=source, capture=Capture())
    assert not form.capture_heading.isHidden()
    assert not form.capture_button.isHidden()
    assert not form.capture_label.isHidden()
    assert form.capture_button.isEnabled()
    assert form.capture_button.text() == "Capture"

    form.capture_screenshot()
    assert isinstance(form._annotation_editor, AnnotationDialog)
    form.reject()


def test_window_attaches_deterministic_capture_bytes_to_callback() -> None:
    _app()
    drafts: list[NewTaskDraft] = []
    controller = BacklogController(
        lambda: [ProjectView("alpha", "Alpha")],
        lambda project, statuses: [],
        lambda draft: drafts.append(draft) or _task("t9", draft.project),
    )
    window = BacklogWindow(controller)
    window.add_button.click()
    form = window._task_form
    assert isinstance(form, TaskFormDialog)
    form._capture_pixmap = QPixmap(10, 10)
    form._capture_pixmap.fill(QColor("red"))
    form.domain_input.setText("ui.avatar")
    form.title_input.setText("Captured task")
    form.submit_task()
    assert drafts[0].screenshot_png is not None
    assert drafts[0].screenshot_png.startswith(b"\x89PNG")
    window.close()


def test_open_capture_form_reuses_existing_form_and_enters_capture_workflow() -> None:
    """Backlog capture reuses one add form and requests annotations each time."""
    _app()
    controller = BacklogController(
        lambda: [ProjectView("alpha", "Alpha")],
        lambda project, statuses: [],
        lambda draft: _task("t1", draft.project),
    )
    window = BacklogWindow(controller)

    with patch.object(TaskFormDialog, "capture_screenshot") as capture:
        window.open_capture_form()
        form = window._task_form
        window.open_capture_form()

    assert isinstance(form, TaskFormDialog)
    assert window._task_form is form
    assert capture.call_count == 2
    assert not window.isVisible()
    form.reject()
    window.close()


def test_backlog_window_remains_visible_after_prior_capture_workflow() -> None:
    """Verify backlog window stays visible when saving/cancelling forms opened from backlog after a prior capture."""
    _app()
    controller = BacklogController(
        lambda: [ProjectView("alpha", "Alpha")],
        lambda project, statuses: [],
        lambda draft: _task("t1", draft.project),
    )
    window = BacklogWindow(controller)

    # 1. Simulate prior direct capture workflow
    with patch.object(TaskFormDialog, "capture_screenshot"):
        window.open_capture_form()
    assert window._single_shot_mode is True

    # 2. User opens the backlog window
    window.show_backlog_window()
    assert window._single_shot_mode is False
    assert window.isVisible()

    # 3. User opens Add Task form from inside backlog window
    window._open_add_form()
    form = window._task_form
    assert isinstance(form, TaskFormDialog)
    assert window._single_shot_mode is False

    # 4. Form is cancelled - window must remain visible
    form.reject()
    assert window.isVisible()
    window.close()


def test_domain_header_toggle_collapse_and_expand() -> None:
    """Domain headers toggle task item visibility when clicked."""
    _app()
    tasks = [
        TaskView("t1", "alpha", "ui.avatar", "Task 1", "Details", "HIGH", TaskStatus.TODO),
        TaskView("t2", "alpha", "ui.avatar", "Task 2", "Details", "LOW", TaskStatus.TODO),
        TaskView("t3", "alpha", "core.voice", "Task 3", "Details", "MEDIUM", TaskStatus.TODO),
    ]
    controller = BacklogController(
        lambda: [ProjectView("alpha", "Alpha")],
        lambda project, statuses: list(tasks),
        lambda draft: tasks[0],
    )
    window = BacklogWindow(controller)
    task_list = window.task_list

    row_t1 = task_list._task_rows["t1"]
    row_t2 = task_list._task_rows["t2"]
    row_t3 = task_list._task_rows["t3"]
    domain_avatar = task_list._domain_rows["ui.avatar"]

    assert not row_t1.item.isHidden()
    assert not row_t2.item.isHidden()
    assert not row_t3.item.isHidden()
    assert domain_avatar.header.expanded is True

    # Toggle collapse for ui.avatar
    domain_avatar.header.set_expanded(False)
    assert row_t1.item.isHidden()
    assert row_t2.item.isHidden()
    assert not row_t3.item.isHidden()

    # Toggle expand for ui.avatar
    domain_avatar.header.set_expanded(True)
    assert not row_t1.item.isHidden()
    assert not row_t2.item.isHidden()
    assert not row_t3.item.isHidden()
