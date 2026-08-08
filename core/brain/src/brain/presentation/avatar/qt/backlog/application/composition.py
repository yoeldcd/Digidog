"""Composition adapter joining the Qt backlog view to application services."""

from __future__ import annotations

import base64
import os
from pathlib import Path

from PySide6.QtWidgets import QWidget

from brain.application.backlog.contracts import CreateTaskRequest
from brain.application.backlog.contracts import EditTaskRequest
from brain.application.backlog.enrichment import enrich_backlog_draft
from brain.application.backlog.models import BacklogTask
from brain.application.backlog.rendering import resolve_task_reference_path
from brain.application.backlog.service import (
    remove_backlog_task,
    set_backlog_task_status,
)
from brain.application.backlog.task_manager import TaskManagerService
from brain.infrastructure.backlog import (
    CanonicalPngAttachmentStore,
    JsonRegisteredProjectCatalog,
)
from brain.infrastructure.runtime.paths import get_brain_mirrors_path
from brain.presentation.avatar.qt.backlog.application.controller import BacklogController
from brain.presentation.avatar.qt.backlog.contracts.models import (
    EditTaskDraft,
    NewTaskDraft,
    ProjectView,
    TaskEditSource,
    TaskEnrichmentDraft,
    TaskEnrichmentResult,
    TaskStatus,
    TaskView,
    backlog_theme,
)
from brain.presentation.avatar.qt.backlog.contracts.ports import TaskDraftEnrichmentPort
from brain.presentation.avatar.qt.backlog.presentation.capture import QtScreenCapture
from brain.presentation.avatar.qt.backlog.presentation.window import BacklogWindow


class _ApplicationTaskDraftEnricher:
    """Adapt the write-free application enrichment service to the native port."""

    def enrich(
        self,
        draft: TaskEnrichmentDraft,
    ) -> TaskEnrichmentResult:
        """Generate one unsaved description proposal through the application service.

        Args:
            draft: Native immutable form values and optional PNG bytes.

        Returns:
            TaskEnrichmentResult: Native immutable description proposal.
        """
        image_data_url = _png_data_url(draft.reference_png)
        task = BacklogTask(
            task_id="draft",
            domain=draft.domain,
            title=draft.title,
            description=draft.description,
            priority=draft.priority,
            status="DRAFT",
        )
        result = enrich_backlog_draft(
            task=task,
            image_data_url=image_data_url,
        )
        return TaskEnrichmentResult(description=result.description)


def _png_data_url(content: bytes | None) -> str | None:
    """Encode an optional PNG attachment in memory for the draft service.

    Args:
        content: Optional PNG bytes held by the form.

    Returns:
        str | None: Data URL suitable for the multimodal application service.
    """
    if content is None:
        return None

    encoded = base64.b64encode(content).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def create_backlog_window(
    parent: QWidget | None = None,
    *,
    theme_mode: str = "light",
) -> BacklogWindow:
    """Create a project-scoped backlog window with avatar-derived theme tokens.

    Args:
        parent: Optional Qt parent that owns the window lifecycle.
        theme_mode: Avatar theme name used to build backlog colors.

    Returns:
        BacklogWindow: Ready-to-show backlog window wired to application services.
    """
    manager = TaskManagerService(
        JsonRegisteredProjectCatalog(get_brain_mirrors_path()),
        CanonicalPngAttachmentStore(),
    )
    controller = _controller_for(manager)
    requested_root = os.environ.get("WORKSPACE_ROOT", "").strip()
    selected_key = _matching_project_key(requested_root, controller.projects)
    if selected_key is not None:
        controller.selected_project = selected_key
        controller.refresh()
    return BacklogWindow(
        controller,
        QtScreenCapture(),
        parent,
        theme=backlog_theme(theme_mode),
        enricher=_ApplicationTaskDraftEnricher(),
    )


def _matching_project_key(
    requested_root: str,
    projects: tuple[ProjectView, ...],
) -> str | None:
    """Match one Windows workspace identity without case-sensitive drift.

    Args:
        requested_root: Workspace path supplied by the active consumer.
        projects: Project projections available to the backlog selector.

    Returns:
        str | None: Matching project key, or ``None`` when no project matches.
    """
    if not requested_root:
        return None
    candidate = os.path.normcase(str(Path(requested_root).expanduser().resolve()))
    for project in projects:
        project_key = os.path.normcase(str(Path(project.key).resolve()))
        if project_key == candidate:
            return project.key
    return None


def _controller_for(manager: TaskManagerService) -> BacklogController:
    """Adapt application DTOs to the narrow Qt view-model callbacks.

    Args:
        manager: Application service that owns project and task operations.

    Returns:
        BacklogController: Controller configured with typed presentation callbacks.
    """

    def load_projects() -> tuple[ProjectView, ...]:
        """Load all registered workspaces for the project selector.

        Returns:
            tuple[ProjectView, ...]: Project projections ordered by the service.
        """
        return tuple(
            ProjectView(project.workspace_root.as_posix(), str(Path(project.workspace_root).resolve()))
            for project in manager.list_projects()
        )

    def load_tasks(
        project_key: str,
        statuses: frozenset[TaskStatus] | None,
    ) -> tuple[TaskView, ...]:
        """Load a complete or status-filtered task projection for one project.

        Args:
            project_key: Workspace key whose backlog is queried.
            statuses: Optional status values; ``None`` requests the complete snapshot.

        Returns:
            tuple[TaskView, ...]: Tasks rendered by the list view.
        """
        selected_statuses = None if statuses is None else frozenset(
            status.value for status in statuses
        )
        return tuple(
            _task_view(project_key, task)
            for task in manager.list_tasks(Path(project_key), selected_statuses)
        )

    def load_edit_source(project_key: str, task_id: str) -> TaskEditSource:
        """Load persisted RAW fields and canonical reference bytes for editing.

        Args:
            project_key: Workspace key owning the selected task.
            task_id: Stable task identifier selected by the user.

        Returns:
            TaskEditSource: Immutable edit-only source data.
        """
        workspace = _registered_workspace(manager, project_key)
        task = next(
            (candidate for candidate in manager.list_tasks(workspace) if candidate.task_id == task_id),
            None,
        )
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        reference_path = resolve_task_reference_path(task_id, workspace)
        reference_png = (
            None
            if reference_path is None
            else (workspace / Path(reference_path)).read_bytes()
        )

        return TaskEditSource(
            project=project_key,
            task_id=task.task_id,
            domain=task.domain,
            title=task.title,
            raw_description=task.description,
            priority=task.priority,
            reference_png=reference_png,
        )

    def create_task(draft: NewTaskDraft) -> TaskView:
        """Persist a new draft and return its presentation projection.

        Args:
            draft: User-entered task values and optional annotated screenshot.

        Returns:
            TaskView: Projection of the newly created task.
        """
        created = manager.create_task(
            CreateTaskRequest(
                workspace_root=Path(draft.project),
                domain=draft.domain,
                title=draft.title,
                description=draft.description,
                priority=draft.priority,
                annotated_png=draft.screenshot_png,
            ),
        )
        return _task_view(draft.project, created.task)

    def edit_task(draft: EditTaskDraft) -> TaskView:
        """Apply editable fields and return the updated task projection.

        Args:
            draft: Selected task and optional replacement fields.

        Returns:
            TaskView: Projection of the updated task.
        """
        updated = manager.edit_task(
            EditTaskRequest(
                workspace_root=Path(draft.project),
                task_id=draft.task_id,
                title=draft.title,
                description=draft.description,
                priority=draft.priority,
                domain=draft.domain,
                annotated_png=draft.screenshot_png,
            ),
        )
        return _task_view(draft.project, updated)

    def change_status(project_key: str, task_id: str, status: TaskStatus) -> TaskView:
        """Persist one lifecycle transition and return the new projection.

        Args:
            project_key: Workspace key containing the task.
            task_id: Stable identifier of the task being changed.
            status: New lifecycle state selected by the user.

        Returns:
            TaskView: Projection after the status transition.
        """
        workspace = _registered_workspace(manager, project_key)
        updated = set_backlog_task_status(workspace, task_id, status.value)
        return _task_view(project_key, updated)

    def delete_task(project_key: str, task_id: str) -> None:
        """Remove one task from its registered workspace.

        Args:
            project_key: Workspace key containing the task.
            task_id: Stable identifier of the task to remove.

        Returns:
            None.
        """
        remove_backlog_task(_registered_workspace(manager, project_key), task_id)

    controller = BacklogController(
        load_projects,
        load_tasks,
        create_task,
        edit_task,
        change_status,
        delete_task,
        load_edit_source=load_edit_source,
    )
    controller.initialize()
    return controller


def _registered_workspace(manager: TaskManagerService, project_key: str) -> Path:
    """Resolve a registered workspace key to its canonical filesystem path.

    Args:
        manager: Application service that owns registered workspace metadata.
        project_key: Workspace key selected by the user.

    Returns:
        Path: Canonical workspace root.

    Raises:
        ValueError: If the key is not registered for this agent core.
    """
    candidate = os.path.normcase(str(Path(project_key).expanduser().resolve()))
    for project in manager.list_projects():
        if os.path.normcase(str(project.workspace_root.resolve())) == candidate:
            return project.workspace_root
    raise ValueError("The requested workspace is not a registered consumer of this agent core.")


def _task_view(project_key: str, task: BacklogTask) -> TaskView:
    """Project one application backlog task into the Qt view contract.

    Args:
        project_key: Workspace key owning the application task.
        task: Application-layer task entity.

    Returns:
        TaskView: Immutable projection consumed by Qt widgets.
    """
    description = task.description
    if "{ref_image}" in description:
        reference_path = resolve_task_reference_path(task.task_id, Path(project_key))
        if reference_path is not None:
            description = description.replace(
                "{ref_image}",
                f"![Task reference]({reference_path})",
            )
    return TaskView(
        task_id=task.task_id,
        project=project_key,
        domain=task.domain,
        title=task.title,
        description=description,
        priority=task.priority,
        status=TaskStatus(task.status),
        created_at=task.created_at,
    )
