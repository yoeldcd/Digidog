"""Registered-project catalog adapter for task management."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Sequence

from brain.application.backlog.contracts import ProjectCatalogError
from brain.application.backlog.contracts import RegisteredProject


class JsonRegisteredProjectCatalog:
    """Read allowlisted consumers from an explicitly injected registry."""

    def __init__(self, registry_path: Path) -> None:
        """Bind the registry path without consulting process-global state."""
        self._registry_path = registry_path.resolve()

    def list_projects(self) -> Sequence[RegisteredProject]:
        """Return normalized projects, deduplicated by resolved root."""
        projects: list[RegisteredProject] = []
        seen_roots: set[str] = set()
        for item in self._read_payload():
            project = _project_from_item(item)
            if project is None:
                continue
            root_key = os.path.normcase(str(project.workspace_root))
            if root_key in seen_roots:
                continue
            seen_roots.add(root_key)
            projects.append(project)
        return tuple(projects)

    def resolve(self, workspace_root: Path) -> RegisteredProject:
        """Resolve an exact root only when registered for this agent core."""
        candidate = workspace_root.expanduser().resolve()
        candidate_key = os.path.normcase(str(candidate))
        for project in self.list_projects():
            project_key = os.path.normcase(str(project.workspace_root))
            if project_key == candidate_key:
                return project
        raise ProjectCatalogError(
            "The requested workspace is not a registered consumer of this agent core.",
        )

    def _read_payload(self) -> list[Any]:
        """Read and validate the top-level registry collection."""
        try:
            payload: Any = json.loads(
                self._registry_path.read_text(encoding="utf-8"),
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise ProjectCatalogError(
                "The Brain mirror registry is unavailable.",
            ) from exc
        if not isinstance(payload, list):
            raise ProjectCatalogError(
                "The Brain mirror registry has an invalid shape.",
            )
        return payload


def _project_from_item(item: Any) -> RegisteredProject | None:
    """Convert one valid registry mapping into a project DTO."""
    if not isinstance(item, dict):
        return None
    name = item.get("name")
    raw_path = item.get("path")
    if not isinstance(name, str) or not name.strip():
        return None
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    return RegisteredProject(
        name=name.strip(),
        workspace_root=Path(raw_path).expanduser().resolve(),
    )