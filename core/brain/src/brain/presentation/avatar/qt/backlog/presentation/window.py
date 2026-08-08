"""Standalone native Qt task-manager window."""
from __future__ import annotations

from collections.abc import Callable
from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from brain.presentation.avatar.qt.backlog.application.controller import BacklogController
from brain.presentation.avatar.qt.backlog.contracts.models import (
    BacklogThemeTokens,
    EditTaskDraft,
    NewTaskDraft,
    TaskView,
    backlog_theme,
)
from brain.presentation.avatar.qt.backlog.contracts.ports import CapturePort, TaskDraftEnrichmentPort
from brain.presentation.avatar.qt.backlog.presentation.detail import TaskDetailPanel
from brain.presentation.avatar.qt.backlog.presentation.filters import BacklogFilterBar
from brain.presentation.avatar.qt.backlog.presentation.form import TaskFormDialog
from brain.presentation.avatar.qt.backlog.presentation.icons import (
    configure_shell_actions,
    svg_icon,
)
from brain.presentation.avatar.qt.backlog.presentation.task_list import BacklogTaskList
from brain.presentation.avatar.qt.backlog.presentation.widgets import (
    backlog_stylesheet,
    popup_stylesheet,
)


class BacklogWindow(QDialog):
    """Project-filtered backlog with list and detail pages plus modeless task forms."""

    def __init__(
        self,
        controller: BacklogController,
        capture: CapturePort | None = None,
        parent: QWidget | None = None,
        theme: BacklogThemeTokens | str = "light",
        enricher: TaskDraftEnrichmentPort | None = None,
    ) -> None:
        """Initialize backlog dialog with controllers, widgets, and theme settings.

        Args:
            controller (BacklogController): Controller handling backlog operations and state.
            capture (CapturePort | None): Optional screenshot capture provider.
            parent (QWidget | None): Optional parent widget container.
            theme (BacklogThemeTokens | str): Theme token model or theme mode string
                ("light" or "dark").
            enricher: Optional presentation port for unsaved description enrichment.


        Returns:
            None.
        """
        super().__init__(parent)
        self.controller = controller
        self.capture = capture


        self.enricher: TaskDraftEnrichmentPort | None = enricher
        self._task_form: TaskFormDialog | None = None
        self._task_form_task: TaskView | None = None
        self._action_message: QMessageBox | None = None
        self._single_shot_mode: bool = False
        self.theme_tokens = backlog_theme("light")
        self.setObjectName("backlogWindow")
        self.setWindowTitle("Task manager")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinMaxButtonsHint,
        )
        self.setModal(False)
        self.setMinimumSize(760, 520)
        self._use_available_screen_geometry()

        self.project_selector = QComboBox(self)
        self.project_selector.setFixedHeight(32)
        self.project_selector.setAccessibleName("Project")
        self.project_selector.setToolTip("Select the task project")
        self.project_selector.setMinimumWidth(240)
        self.project_selector.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.search_input = QLineEdit(self)
        self.search_input.setObjectName("taskSearch")

        self.search_input.setPlaceholderText("Search tasks")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setAccessibleName("Search tasks")
        self.search_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.search_input.setToolTip(
            "Filter tasks by id, domain, title, status, priority, or content",
        )
        self.search_action = self.search_input.addAction(
            svg_icon("search", "#66505e", 17),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.refresh_button = QPushButton(self)
        self.refresh_button.setFixedHeight(32)
        self.refresh_button.setProperty("compactAction", True)
        self.add_button = QPushButton("Add task", self)
        self.add_button.setFixedHeight(32)
        self.add_button.setProperty("primaryAction", True)

        self.task_list = BacklogTaskList(self.theme_tokens, parent=self)
        self.task_list.setObjectName("taskList")
        self.task_list.setAccessibleName("Tasks")
        self.task_list.setSpacing(2)
        self.task_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.detail_panel = TaskDetailPanel(self)
        self.detail_panel.dismissed.connect(self._show_task_list_page)
        self._build_layout()
        self._connect_events()
        self.set_theme(theme)
        self.reload_projects()

    def _build_layout(self) -> None:
        """Assemble main stacked page navigation layout.

        Returns:
            None.
        """
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        self.page_stack = QStackedWidget(self)
        self.page_stack.setObjectName("backlogPages")
        root.addWidget(self.page_stack, 1)

        self.list_page = QWidget(self.page_stack)
        self.list_page.setObjectName("listPage")
        list_layout = QVBoxLayout(self.list_page)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(5)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(7)
        toolbar.addWidget(self.project_selector, 1)
        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.add_button)
        list_layout.addLayout(toolbar)
        self.filter_bar = BacklogFilterBar(
            self.controller.statuses,
            self.controller.priorities,
            self.list_page,
            search_widget=self.search_input,
        )
        self.status_buttons = self.filter_bar.status_buttons
        self.priority_buttons = self.filter_bar.priority_buttons
        self.sort_buttons = self.filter_bar.sort_buttons
        self.sort_button_group = self.filter_bar.sort_button_group
        list_layout.addWidget(self.filter_bar)
        list_layout.addWidget(self.task_list, 1)

        self.page_stack.addWidget(self.list_page)
        self.page_stack.addWidget(self.detail_panel)

    def _connect_events(self) -> None:
        """Bind signal handlers for user interactions across controls and panels.

        Returns:
            None.
        """
        self.project_selector.currentIndexChanged.connect(self._project_changed)
        self.search_input.textChanged.connect(self.task_list.set_query)
        self.refresh_button.clicked.connect(self.reload_projects)
        self.add_button.clicked.connect(self._open_add_form)
        self.task_list.itemClicked.connect(self.show_task_detail)
        self.detail_panel.start_requested.connect(
            lambda task: self._mutate_detail(lambda: self.controller.start_work(task)),
        )
        self.detail_panel.done_requested.connect(
            lambda task: self._mutate_detail(lambda: self.controller.mark_done(task)),
        )
        self.detail_panel.edit_requested.connect(self._open_edit_form)
        self.detail_panel.delete_requested.connect(self._delete_detail)
        for button in self.status_buttons.values():
            button.toggled.connect(self._filters_changed)
        for button in self.priority_buttons.values():
            button.toggled.connect(self._filters_changed)
        for newest, button in self.sort_buttons.items():
            button.toggled.connect(
                lambda checked, value=newest: self._sort_changed(value, checked),
            )

    def set_theme(self, theme: BacklogThemeTokens | str) -> None:
        """Apply modern theme, semantic icons, and strong interaction states.

        Args:
            theme: Theme token object or theme mode string ("light" or "dark").

        Returns:
            None.
        """
        self.theme_tokens = backlog_theme(theme) if isinstance(theme, str) else theme
        tokens = self.theme_tokens
        self.setProperty("avatarTheme", tokens.mode)
        self.setStyleSheet(backlog_stylesheet(tokens))
        self.search_action.setIcon(svg_icon("search", tokens.muted, 17))
        configure_shell_actions(
            refresh_button=self.refresh_button,
            add_button=self.add_button,
            capture_button=None,
            cancel_button=None,
            submit_button=None,
            status_buttons=self.status_buttons,
            priority_buttons=self.priority_buttons,
            sort_buttons=self.sort_buttons,
            tokens=tokens,
        )
        self._apply_combo_popup_theme(tokens)
        form = self._task_form
        if form is not None:
            form.set_theme(tokens)
        self.detail_panel.set_theme(tokens)
        self.task_list.set_theme(tokens)

    def _apply_combo_popup_theme(self, tokens: BacklogThemeTokens) -> None:
        """Apply popup menu stylesheet styling to the project selector.

        Args:
            tokens: Theme token configuration.

        Returns:
            None.
        """
        popup_style = popup_stylesheet(tokens)
        self.project_selector.view().setStyleSheet(popup_style)

    def reload_projects(self) -> None:
        """Reload available project list from repository and populate selection dropdown.

        Returns:
            None.
        """
        self.project_selector.blockSignals(True)
        self.project_selector.clear()
        self.controller.initialize()
        for project in self.controller.projects:
            self.project_selector.addItem(project.label, project.key)
        selected = self.project_selector.findData(self.controller.selected_project)
        self.project_selector.setCurrentIndex(max(0, selected))
        self.project_selector.blockSignals(False)
        self._sync_domain_suggestions()
        self._render_tasks(self.controller.tasks)
        self._show_task_list_page()

    def _project_changed(self, index: int) -> None:
        """Handle project dropdown selection change event.

        Args:
            index (int): Selected dropdown item index.

        Returns:
            None.
        """
        project = self.project_selector.itemData(index)
        if project:
            self._render_tasks(self.controller.select_project(str(project)))
            self._sync_domain_suggestions()

    def _filters_changed(self, *_args: object) -> None:
        """Re-evaluate active filter button states and update visible task list.

        Args:
            *_args (object): Ignored event signal parameters.

        Returns:
            None.
        """
        statuses = frozenset(
            status
            for status, button in self.status_buttons.items()
            if button.isChecked()
        )
        priorities = frozenset(
            priority
            for priority, button in self.priority_buttons.items()
            if button.isChecked()
        )
        self.task_list.set_filters(statuses, priorities)
        self._render_tasks(self.controller.set_filters(statuses, priorities))

    def _sort_changed(self, newest: bool, checked: bool) -> None:
        """Update task sort ordering direction when sort button toggles.

        Args:
            newest (bool): True if newest-first ordering is active.
            checked (bool): True if sort button became checked.

        Returns:
            None.
        """
        if checked:
            self.task_list.set_sort_newest_first(newest)

    def show_backlog_window(self) -> None:
        """Show and focus the backlog task-list window, resetting single-shot mode."""
        self._single_shot_mode = False
        self.show()
        self.raise_()
        self.activateWindow()

    def refresh_tasks(self) -> None:
        """Fetch latest tasks from repository and refresh view list.

        Returns:
            None.
        """
        self._render_tasks(self.controller.refresh())

    def _render_tasks(self, tasks: tuple[TaskView, ...]) -> None:
        """Reconcile the complete task snapshot into the stable list widget.

        Args:
            tasks: Complete task projections for the selected project.
        """
        self.task_list.set_filters(self.controller.statuses, self.controller.priorities)
        self.task_list.set_tasks(tasks)

    def show_task_detail(self, item: QListWidgetItem) -> None:
        """Switch to detail panel page and render selected task item.

        Args:
            item (QListWidgetItem): Clicked list item holding task data.

        Returns:
            None.
        """
        task = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(task, TaskView):
            return
        self.detail_panel.set_task(task)
        self.page_stack.setCurrentWidget(self.detail_panel)

    def _mutate_detail(self, operation: Callable[[], TaskView]) -> None:
        """Execute a task mutation callback and update task detail views.

        Args:
            operation (Callable[[], TaskView]): Mutating controller operation.

        Returns:
            None.
        """
        try:
            updated = operation()
        except ValueError as error:
            self._show_action_error(error)
            return
        self._sync_domain_suggestions()
        self._render_tasks(self.controller.tasks)
        self.detail_panel.set_task(updated)

    def _delete_detail(self, task: TaskView) -> None:
        """Prompt confirmation and delete task from repository.

        Args:
            task (TaskView): Task view model to delete.

        Returns:
            None.
        """
        answer = QMessageBox.question(
            self, "Delete task", f"Delete {task.task_id}: {task.title}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.controller.delete(task)
        except ValueError as error:
            self._show_action_error(error)
            return
        self._sync_domain_suggestions()
        self._render_tasks(self.controller.tasks)
        self._show_task_list_page()

    def _show_action_error(self, error: ValueError) -> None:
        """Display non-modal error message box for failed task actions.

        Args:
            error (ValueError): Action error exception.

        Returns:
            None.
        """
        message = QMessageBox(self)
        message.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        message.setWindowTitle("Task action failed")
        message.setIcon(QMessageBox.Icon.Warning)
        message.setText(str(error))
        message.setStandardButtons(QMessageBox.StandardButton.Ok)
        message.setWindowModality(Qt.WindowModality.NonModal)
        self._action_message = message
        message.finished.connect(lambda _result: setattr(self, "_action_message", None))
        message.show()

    def _show_task_list_page(self) -> None:
        """Switch stacked widget view to main task list page.

        Returns:
            None.
        """
        self.page_stack.setCurrentWidget(self.list_page)
        self.task_list.setFocus()

    def _open_add_form(self) -> None:
        """Open the modeless add-task form for the selected project."""
        if self._task_form is not None:
            self._focus_task_form()
            return

        form = TaskFormDialog(
            project=self.controller.selected_project,
            capture=self.capture,
            parent=None,
            theme=self.theme_tokens,
            enricher=self.enricher,
        )
        self._show_task_form(form, None)

    def open_capture_form(self) -> None:
        """Focus one add form and immediately enter its annotation workflow."""
        self._single_shot_mode = True
        self._open_add_form()
        if self._task_form is not None:
            self._task_form.capture_screenshot()

    def _open_edit_form(self, task: TaskView) -> None:
        """Open the modeless edit form for a selected task.

        Args:
            task: Task view that owns the edit request.
        """
        self._single_shot_mode = False
        if self._task_form is not None:
            self._focus_task_form()
            return

        try:
            edit_source = self.controller.load_edit_source(task)
        except ValueError as error:
            self._show_action_error(error)
            return

        form = TaskFormDialog(
            edit_source=edit_source,
            capture=self.capture,
            parent=None,
            theme=self.theme_tokens,
            enricher=self.enricher,
        )
        self._show_task_form(form, task)

    def _show_task_form(
        self,
        form: TaskFormDialog,
        task: TaskView | None,
    ) -> None:
        """Connect, initialize, and show one parentless task form."""
        self._task_form = form
        self._task_form_task = task
        form.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        form.set_domain_suggestions(self.controller.domain_suggestions)
        form.create_requested.connect(self._submit_new_task)
        form.edit_requested.connect(self._submit_task_edit)
        form.cancelled.connect(self._task_form_cancelled)
        form.finished.connect(partial(self._release_task_form, form))
        form.destroyed.connect(partial(self._release_task_form, form))
        form.show()
        form.raise_()
        form.activateWindow()

    def _focus_task_form(self) -> None:
        """Raise the active task form without creating another dialog."""
        form = self._task_form
        if form is None:
            return

        form.show()
        form.raise_()
        form.activateWindow()

    def _release_task_form(
        self,
        form: TaskFormDialog,
        _event: object | None = None,
    ) -> None:
        """Release references when a task form finishes or is destroyed."""
        if form is not self._task_form:
            return

        self._task_form = None
        self._task_form_task = None

    def _task_form_cancelled(self) -> None:
        """Return to the task list after the form is cancelled."""
        if self._single_shot_mode:
            self._single_shot_mode = False
            self.hide()
        else:
            self._show_task_list_page()
            self.show()
            self.raise_()
            self.activateWindow()

    def cancel_add(self) -> None:
        """Reject the active form and return to the task list."""
        form = self._task_form
        if form is not None:
            form.reject()

    def _submit_new_task(self, draft: NewTaskDraft) -> None:
        """Submit a new task draft and close its form after success.

        Args:
            draft: Validated new-task draft emitted by the form.
        """
        form = self._task_form
        if form is None:
            return

        try:
            self.controller.submit(draft)
        except ValueError as error:
            form.show_error(error)
            return

        form.accept()
        self._sync_domain_suggestions()
        self._render_tasks(self.controller.tasks)
        if self._single_shot_mode:
            self._single_shot_mode = False
            self.hide()
        else:
            self._show_task_list_page()
            self.show()
            self.raise_()
            self.activateWindow()

    def _submit_task_edit(self, draft: EditTaskDraft) -> None:
        """Submit an edit draft for the form selected task.

        Args:
            draft: Validated edit draft emitted by the form.
        """
        form = self._task_form
        task = self._task_form_task
        if form is None or task is None:
            return

        try:
            updated = self.controller.edit(task, draft)
        except ValueError as error:
            form.show_error(error)
            return

        form.accept()
        self._sync_domain_suggestions()
        self._render_tasks(self.controller.tasks)
        if self._single_shot_mode:
            self._single_shot_mode = False
            self.hide()
        else:
            self.detail_panel.set_task(updated)
            self.page_stack.setCurrentWidget(self.detail_panel)
            self.show()
            self.raise_()
            self.activateWindow()

    def _sync_domain_suggestions(self) -> None:
        """Update the active form with current project suggestions."""
        form = self._task_form
        if form is None:
            return

        form.set_domain_suggestions(self.controller.domain_suggestions)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Reject an active task form before closing the main window.

        Args:
            event: Qt close event delivered to this window.
        """
        form = self._task_form
        if form is not None:
            form.reject()

        super().closeEvent(event)

    def _use_available_screen_geometry(self) -> None:
        """Position window using active screen available geometry.

        Returns:
            None.
        """
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            self.resize(1100, 720)
            return
        self.setGeometry(screen.availableGeometry())

