"""Narrow ports protecting the task manager from infrastructure details."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from PySide6.QtGui import QPixmap

from brain.presentation.avatar.qt.backlog.contracts.models import (
    EditTaskDraft,
    NewTaskDraft,
    ProjectView,
    TaskEditSource,
    TaskEnrichmentDraft,
    TaskEnrichmentResult,
    TaskStatus,
    TaskView,
)


class CapturePort(Protocol):
    """Capture port consumed by the backlog task-creation workflow."""

    def capture(self) -> QPixmap:
        """Capture the visible workspace without presentation overlays.

        Returns:
            QPixmap: Screenshot image available for annotation or attachment.
        """
        ...


ProjectLoader = Callable[[], Sequence[ProjectView]]
TaskLoader = Callable[[str, frozenset[TaskStatus] | None], Sequence[TaskView]]
TaskEditSourceLoader = Callable[[str, str], TaskEditSource]
TaskCreator = Callable[[NewTaskDraft], TaskView]
TaskEditor = Callable[[EditTaskDraft], TaskView]
TaskStatusChanger = Callable[[str, str, TaskStatus], TaskView]
TaskDeleter = Callable[[str, str], None]


class TaskDraftEnrichmentPort(Protocol):
    """Presentation-owned port for unsaved task-description enrichment."""

    def enrich(
        self,
        draft: TaskEnrichmentDraft,
    ) -> TaskEnrichmentResult:
        """Generate a description proposal without persisting the task.

        Args:
            draft: Immutable form values and optional in-memory PNG reference.

        Returns:
            TaskEnrichmentResult: Generated description proposal.
        """
        ...
