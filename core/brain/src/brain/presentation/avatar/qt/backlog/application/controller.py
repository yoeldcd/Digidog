"""Toolkit-light controller for task-manager state and coordination."""
from __future__ import annotations

from brain.presentation.avatar.qt.backlog.contracts.models import (
    EditTaskDraft,
    NewTaskDraft,
    ProjectView,
    TaskPriority,
    TaskEditSource,
    TaskStatus,
    TaskView,
)
from brain.presentation.avatar.qt.backlog.contracts.ports import (
    ProjectLoader,
    TaskCreator,
    TaskDeleter,
    TaskEditor,
    TaskEditSourceLoader,
    TaskLoader,
    TaskStatusChanger,
)


class BacklogActionError(ValueError):
    """Raised when a selected-task action violates the view-state contract."""


class BacklogController:
    """Coordinate project selection, filtering, refresh, and submission."""

    def __init__(
        self,
        load_projects: ProjectLoader,
        load_tasks: TaskLoader,
        create_task: TaskCreator,
        edit_task: TaskEditor | None = None,
        change_status: TaskStatusChanger | None = None,
        delete_task: TaskDeleter | None = None,
        load_edit_source: TaskEditSourceLoader | None = None,
    ) -> None:
        """Initialize callbacks and the current project/filter projection.

        Args:
            load_projects: Callback returning registered project projections.
            load_tasks: Callback loading tasks for a project and status set.
            create_task: Callback persisting a new task draft.
            edit_task: Optional callback updating an existing task.
            change_status: Optional callback changing task lifecycle state.
            delete_task: Optional callback deleting an existing task.
            load_edit_source: Optional callback loading RAW edit data and reference bytes.
        """
        self._load_projects = load_projects
        self._load_tasks = load_tasks
        self._create_task = create_task
        self._edit_task = edit_task
        self._change_status = change_status
        self._delete_task = delete_task
        self._load_edit_source = load_edit_source
        self.projects: tuple[ProjectView, ...] = ()
        self.selected_project = ""
        self.statuses = frozenset({TaskStatus.TODO, TaskStatus.WORKING})
        self.priorities = frozenset(TaskPriority)
        self.domain_suggestions: tuple[str, ...] = ()
        self._task_snapshot: tuple[TaskView, ...] = ()
        self.tasks: tuple[TaskView, ...] = ()

    def initialize(self) -> tuple[TaskView, ...]:
        """Load projects, select a valid default, and refresh visible tasks.

        Returns:
            tuple[TaskView, ...]: Tasks visible after initial filtering.
        """
        self.projects = tuple(self._load_projects())
        keys = {item.key for item in self.projects}
        if self.projects and self.selected_project not in keys:
            self.selected_project = self.projects[0].key
        self._refresh_domain_suggestions()
        return self.refresh()

    def select_project(self, project: str) -> tuple[TaskView, ...]:
        """Select a registered project and refresh its filtered task list.

        Args:
            project: Stable workspace key selected in the project control.

        Returns:
            tuple[TaskView, ...]: Tasks visible for the selected project.

        Raises:
            ValueError: If the project key is not registered.
        """
        if project not in {item.key for item in self.projects}:
            raise ValueError(f"Unknown project: {project}")
        self.selected_project = project
        self._refresh_domain_suggestions()
        return self.refresh()

    def set_statuses(self, statuses: frozenset[TaskStatus]) -> tuple[TaskView, ...]:
        """Store local status filter state without loader I/O.

        Args:
            statuses: Status values enabled by the user.

        Returns:
            tuple[TaskView, ...]: Complete loaded TaskView snapshot for Qt-side filtering.
        """
        return self.set_filters(statuses, self.priorities)

    def set_priorities(self, priorities: frozenset[TaskPriority]) -> tuple[TaskView, ...]:
        """Store local priority filter state without loader I/O.

        Args:
            priorities: Priority values enabled by the user.

        Returns:
            tuple[TaskView, ...]: Complete loaded TaskView snapshot for Qt-side filtering.
        """
        return self.set_filters(self.statuses, priorities)

    def set_filters(
        self,
        statuses: frozenset[TaskStatus],
        priorities: frozenset[TaskPriority],
    ) -> tuple[TaskView, ...]:
        """Store status and priority selections without reloading task data.

        Args:
            statuses: Status values enabled in the list view.
            priorities: Priority values enabled in the list view.

        Returns:
            tuple[TaskView, ...]: Complete loaded task snapshot for Qt-side filtering.
        """
        self.statuses = statuses
        self.priorities = priorities
        self.tasks = self._task_snapshot
        return self.tasks

    def refresh(self) -> tuple[TaskView, ...]:
        """Reload and store one complete project snapshot for the selected project.

        Returns:
            tuple[TaskView, ...]: Complete task snapshot consumed by the Qt list.
        """
        if not self.selected_project:
            self._task_snapshot = ()
            self.tasks = ()
            return self.tasks
        self._task_snapshot = tuple(self._load_tasks(self.selected_project, None))
        self.tasks = self._task_snapshot
        return self.tasks

    def submit(self, draft: NewTaskDraft) -> TaskView:
        """Validate, persist, and project a newly entered task draft.

        Args:
            draft: User-entered task fields and optional screenshot attachment.

        Returns:
            TaskView: Projection returned by the create callback.

        Raises:
            ValueError: If project, domain, or title is blank.
        """
        if not draft.project or not draft.domain.strip() or not draft.title.strip():
            raise ValueError("Project, domain, and title are required.")
        created = self._create_task(draft)
        self._refresh_domain_suggestions()
        self.refresh()
        return created

    def load_edit_source(self, task: TaskView) -> TaskEditSource:
        """Load RAW editable data for the selected task only.

        Args:
            task: Selected rendered task projection.

        Returns:
            TaskEditSource: Raw fields and optional canonical reference bytes.
        """
        self._require_selected(task)
        if self._load_edit_source is None:
            raise BacklogActionError("Task edit loading is unavailable.")

        return self._load_edit_source(task.project, task.task_id)

    def edit(self, task: TaskView, draft: EditTaskDraft) -> TaskView:
        """Edit allowed fields of the selected workspace-local task.

        Args:
            task (TaskView): Currently selected task view item.
            draft (EditTaskDraft): Validated draft containing fields to edit.

        Returns:
            TaskView: Updated task view instance.
        """
        self._require_selected(task)
        if draft.project != task.project or draft.task_id != task.task_id:
            raise BacklogActionError("The edit target does not match the selected task.")
        if self._edit_task is None:
            raise BacklogActionError("Task editing is unavailable.")
        updated = self._edit_task(draft)
        self._refresh_domain_suggestions()
        self.refresh()
        return updated

    def start_work(self, task: TaskView) -> TaskView:
        """Move the selected task into the working state.

        Args:
            task: Task projection currently selected in the list.

        Returns:
            TaskView: Projection returned after the status change.
        """
        return self._set_selected_status(task, TaskStatus.WORKING)

    def mark_done(self, task: TaskView) -> TaskView:
        """Mark the selected task as complete.

        Args:
            task: Task projection currently selected in the list.

        Returns:
            TaskView: Projection returned after the status change.
        """
        return self._set_selected_status(task, TaskStatus.DONE)

    def delete(self, task: TaskView) -> None:
        """Delete the selected task from its project.

        Args:
            task: Task projection currently selected in the list.

        Returns:
            None.
        """
        self._require_selected(task)
        if self._delete_task is None:
            raise BacklogActionError("Task deletion is unavailable.")
        self._delete_task(task.project, task.task_id)
        self._refresh_domain_suggestions()
        self.refresh()

    def _set_selected_status(self, task: TaskView, status: TaskStatus) -> TaskView:
        """Apply a workflow transition after validating the selected task.

        Args:
            task: Task projection currently selected in the list.
            status: Target lifecycle state.

        Returns:
            TaskView: Updated task projection.

        Raises:
            BacklogActionError: If selection, transition, or callback is invalid.
        """
        self._require_selected(task)
        if task.status is TaskStatus.DONE:
            raise BacklogActionError("Completed tasks cannot change workflow state.")
        if self._change_status is None:
            raise BacklogActionError("Task status changes are unavailable.")
        updated = self._change_status(task.project, task.task_id, status)
        self.refresh()
        return updated

    def _require_selected(self, task: TaskView) -> None:
        """Ensure an action targets the currently selected project.

        Args:
            task: Task projection supplied by a list or detail action.

        Returns:
            None.

        Raises:
            BacklogActionError: If the task is outside the selected project.
        """
        if not self.selected_project or task.project != self.selected_project:
            raise BacklogActionError("The task does not belong to the selected project.")

    def _refresh_domain_suggestions(self) -> None:
        """Collect project-local domain suggestions independently of visible filters.

        Returns:
            None.
        """
        if not self.selected_project:
            self.domain_suggestions = ()
            return
        all_tasks = self._load_tasks(self.selected_project, frozenset(TaskStatus))
        self.domain_suggestions = tuple(
            sorted(
                {task.domain.strip() for task in all_tasks if task.domain.strip()},
                key=str.casefold,
            ),
        )
