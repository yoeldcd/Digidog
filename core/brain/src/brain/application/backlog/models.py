# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Backlog domain models."""

from __future__ import annotations

# Standard Libraries Imports
from dataclasses import dataclass


TASK_STATUSES = frozenset({"TODO", "WORKING", "DONE"})
"""Supported persisted task states."""


@dataclass(slots=True, frozen=True)
class BacklogTask:
    """One durable backlog task stored in the workspace logs database."""

    task_id: str
    domain: str
    title: str
    description: str
    priority: str
    status: str
    completed_at: str = ""
    created_at: float = 0.0

    @property
    def done(self) -> bool:
        """Return whether the task has been completed."""
        return self.status == "DONE"

    def as_mapping(self) -> dict[str, object]:
        """Return the legacy-compatible shape used by the tree renderer."""
        return {
            "id": self.task_id,
            "priority": self.priority,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "checked": self.done,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
        }


class TaskNode:
    """A node in the task domain hierarchy tree."""

    def __init__(self, name: str, level: int) -> None:
        self.name = name
        self.level = level
        self.tasks: list[dict[str, object]] = []
        self.children: dict[str, TaskNode] = {}

    def is_empty(self) -> bool:
        """Return True if this node has no tasks and no non-empty descendants."""
        return not self.tasks and not any(not child.is_empty() for child in self.children.values())
