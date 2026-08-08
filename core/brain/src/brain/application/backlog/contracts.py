"""Typed contracts for workspace-explicit task management."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from brain.application.backlog.models import BacklogTask


class TaskManagerError(ValueError):
    """Base error exposed by the task-manager application boundary."""


class ProjectCatalogError(TaskManagerError):
    """Raised when the registered-project catalog cannot satisfy a request."""


class AttachmentValidationError(TaskManagerError):
    """Raised when a task attachment is not a supported PNG."""


class AttachmentPersistenceError(TaskManagerError):
    """Raised when a validated attachment cannot be persisted."""


@dataclass(frozen=True, slots=True)
class RegisteredProject:
    """One registered consumer workspace."""

    name: str
    workspace_root: Path


@dataclass(frozen=True, slots=True)
class CreateTaskRequest:
    """Input for creating one workspace-local backlog task."""

    workspace_root: Path
    domain: str
    title: str
    description: str
    priority: str = "LOW"
    annotated_png: bytes | None = None


@dataclass(frozen=True, slots=True)
class CreatedTask:
    """Created task and its optional canonical attachment path."""

    task: BacklogTask
    attachment_path: Path | None


@dataclass(frozen=True, slots=True)
class EditTaskRequest:
    """Input for editing one workspace-local backlog task."""

    workspace_root: Path
    task_id: str
    domain: str | None = None
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    annotated_png: bytes | None = None


class ProjectCatalog(Protocol):
    """Resolve consumer roots through an allowlisted project catalog."""

    def list_projects(self) -> Sequence[RegisteredProject]:
        """Return all valid registered projects."""
        ...

    def resolve(self, workspace_root: Path) -> RegisteredProject:
        """Return the project matching an explicit workspace root."""
        ...


class PngAttachmentStore(Protocol):
    """Validate and persist canonical PNG task attachments."""

    def validate(self, content: bytes) -> None:
        """Validate PNG content without writing it."""
        ...

    def discard(self, workspace_root: Path, task_id: str) -> None:
        """Remove any stale canonical attachment for a task ID."""
        ...

    def save(self, workspace_root: Path, task_id: str, content: bytes) -> Path:
        """Persist PNG content for an already-created task ID."""
        ...