"""Workspace-explicit task-manager application controller."""

from __future__ import annotations

from pathlib import Path

from brain.application.backlog.contracts import AttachmentPersistenceError
from brain.application.backlog.contracts import CreatedTask
from brain.application.backlog.contracts import CreateTaskRequest
from brain.application.backlog.contracts import EditTaskRequest
from brain.application.backlog.contracts import PngAttachmentStore
from brain.application.backlog.contracts import ProjectCatalog
from brain.application.backlog.contracts import RegisteredProject
from brain.application.backlog.models import BacklogTask
from brain.application.backlog.rendering import resolve_task_reference_path
from brain.application.backlog.models import TASK_STATUSES
from brain.application.backlog.service import create_backlog_task
from brain.application.backlog.service import edit_backlog_task
from brain.application.backlog.service import get_backlog_task
from brain.application.backlog.service import list_backlog_tasks
from brain.application.backlog.service import remove_backlog_task


class TaskManagerService:
    """Coordinate project selection, task operations, and attachments."""

    def __init__(
        self,
        project_catalog: ProjectCatalog,
        attachment_store: PngAttachmentStore,
    ) -> None:
        """Bind narrow catalog and attachment ports."""
        self._project_catalog = project_catalog
        self._attachment_store = attachment_store

    def list_projects(self) -> tuple[RegisteredProject, ...]:
        """Return registered consumers without process-global workspace state."""
        return tuple(self._project_catalog.list_projects())

    def list_tasks(
        self,
        workspace_root: Path,
        statuses: frozenset[str] | None = None,
    ) -> tuple[BacklogTask, ...]:
        """Return tasks from one registered consumer, filtered by status."""
        project = self._project_catalog.resolve(workspace_root)
        selected_statuses = _normalize_statuses(statuses)
        tasks = list_backlog_tasks(project.workspace_root, show_all=True)
        if selected_statuses is None:
            return tuple(tasks)
        return tuple(task for task in tasks if task.status in selected_statuses)

    def create_task(self, request: CreateTaskRequest) -> CreatedTask:
        """Create one task and persist its optional validated PNG."""
        project = self._project_catalog.resolve(request.workspace_root)
        if request.annotated_png is not None:
            self._attachment_store.validate(request.annotated_png)
        task = create_backlog_task(
            project.workspace_root,
            request.domain,
            request.title,
            _with_reference_marker(request.description, request.annotated_png),
            request.priority,
        )
        try:
            self._attachment_store.discard(
                project.workspace_root,
                task.task_id,
            )
            if request.annotated_png is None:
                return CreatedTask(task=task, attachment_path=None)
            attachment_path = self._attachment_store.save(
                project.workspace_root,
                task.task_id,
                request.annotated_png,
            )
        except (AttachmentPersistenceError, OSError) as exc:
            remove_backlog_task(project.workspace_root, task.task_id, force=True)
            if isinstance(exc, AttachmentPersistenceError):
                raise
            raise AttachmentPersistenceError(
                "The task attachment lifecycle could not be completed.",
            ) from exc
        return CreatedTask(task=task, attachment_path=attachment_path)

    def edit_task(self, request: EditTaskRequest) -> BacklogTask:
        """Edit one task and restore its prior state if PNG replacement fails."""
        project = self._project_catalog.resolve(request.workspace_root)
        previous_task = get_backlog_task(project.workspace_root, request.task_id)
        previous_png = _read_reference_png(previous_task.task_id, project.workspace_root)
        annotated_png = request.annotated_png

        if annotated_png is not None:
            self._attachment_store.validate(annotated_png)

        description = _with_reference_marker(request.description, annotated_png)
        updated_task = edit_backlog_task(
            project.workspace_root,
            request.task_id,
            title=request.title,
            description=description,
            priority=request.priority,
            domain=request.domain,
        )

        if annotated_png is None:
            return updated_task

        try:
            self._attachment_store.save(
                project.workspace_root,
                updated_task.task_id,
                annotated_png,
            )
        except (AttachmentPersistenceError, OSError) as exc:
            _restore_task(project.workspace_root, previous_task)
            _restore_reference_png(
                self._attachment_store,
                project.workspace_root,
                previous_task.task_id,
                previous_png,
            )
            if isinstance(exc, AttachmentPersistenceError):
                raise
            raise AttachmentPersistenceError(
                "The task attachment lifecycle could not be completed.",
            ) from exc

        return updated_task


def _with_reference_marker(description: str | None, annotated_png: bytes | None) -> str | None:
    """Append the canonical image marker exactly once when an image is supplied."""
    if annotated_png is None or description is None or "{ref_image}" in description:
        return description

    stripped_description = description.rstrip()
    if not stripped_description:
        return "{ref_image}"

    return f"{stripped_description}\n\n{{ref_image}}"


def _read_reference_png(task_id: str, workspace_root: Path) -> bytes | None:
    """Return existing canonical attachment bytes when present."""
    relative_path = resolve_task_reference_path(task_id, workspace_root)
    if relative_path is None:
        return None

    return (workspace_root / Path(relative_path)).read_bytes()


def _restore_task(workspace_root: Path, task: BacklogTask) -> None:
    """Restore editable persisted fields after an attachment failure."""
    edit_backlog_task(
        workspace_root,
        task.task_id,
        title=task.title,
        description=task.description,
        priority=task.priority,
        domain=task.domain,
    )


def _restore_reference_png(
    store: PngAttachmentStore,
    workspace_root: Path,
    task_id: str,
    content: bytes | None,
) -> None:
    """Restore prior attachment bytes or remove a newly created attachment."""
    if content is None:
        store.discard(workspace_root, task_id)
        return

    store.save(workspace_root, task_id, content)


def _normalize_statuses(
    statuses: frozenset[str] | None,
) -> frozenset[str] | None:
    """Normalize and validate an optional task-status selection."""
    if statuses is None:
        return None
    normalized = frozenset(str(value).strip().upper() for value in statuses)
    unsupported = normalized - TASK_STATUSES
    if unsupported:
        raise ValueError(f"Unsupported task status: {sorted(unsupported)[0]}")
    return normalized