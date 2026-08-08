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
    """One durable backlog task stored in the workspace logs database.

    Attributes:
        task_id: `str`. The unique identifier for the task.
        domain: `str`. The domain category associated with the task.
        title: `str`. The brief title of the task.
        description: `str`. The detailed description of the task.
        priority: `str`. The priority level assigned to the task.
        status: `str`. The current state of the task, typically one of the supported persisted task states.
        completed_at: `str`. The timestamp indicating when the task was completed.
        created_at: `float`. The epoch timestamp indicating when the task was created.
    """

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
        """Return whether the task has been completed.

        Returns:
            bool: A boolean indicating whether the task status is set to DONE.
        """
        return self.status == "DONE"

    def as_mapping(self) -> dict[str, object]:
        """Return the legacy-compatible shape used by the tree renderer.

        Returns:
            dict[str, object]: A mapping of task attributes to their corresponding values.
        """
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
        """Return True if this node has no tasks and no non-empty descendants.

        Returns:
            bool: A boolean indicating if the node and its subtree are devoid of tasks.
        """
        return not self.tasks and not any(not child.is_empty() for child in self.children.values())
