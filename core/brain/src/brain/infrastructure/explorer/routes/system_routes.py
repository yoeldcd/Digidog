"""SystemRoutesMixin for Brain Explorer."""

from __future__ import annotations

from typing import Any

from brain.infrastructure.explorer.resources import find_documentation_dirs
from brain.infrastructure.explorer.validation import load_registered_projects
from brain.infrastructure.runtime.paths import (
    get_agent_home,
    get_core_root,
    get_workspace_root,
)


class SystemRoutesMixin:
    """Provide one cohesive group of Explorer routes."""

    def _health_payload(self) -> dict[str, Any]:
        """
        Return server health metadata.

        Returns:
            dict[str, Any]: Health payload.
        """
        return {
            "ok": True,
            "name": "brain_explorer",
            "distDir": self.config.dist_dir.as_posix(),
            "workspaceRoot": get_workspace_root().as_posix(),
            "agentHome": get_agent_home().as_posix(),
            "coreRoot": get_core_root().as_posix(),
        }

    def _projects_list(self) -> dict[str, Any]:
        """Return the list of registered projects from brain_mirrors.json."""
        return {"ok": True, "projects": load_registered_projects()}

    def _wikis_list(self) -> dict[str, Any]:
        """
        Scan workspace root for documentation directories, check if they have
        compiled wiki folders, and return the list.
        """
        workspace_root = get_workspace_root()
        doc_dirs = find_documentation_dirs(workspace_root)
        wikis = []
        for d in doc_dirs:
            wiki_name = d.parent.name
            wiki_index = d / "wiki" / "index.html"
            wiki_data = d / "wiki" / "data" / "index.json"
            has_wiki = wiki_index.exists() and wiki_data.exists()
            wikis.append({
                "name": wiki_name,
                "path": d.as_posix(),
                "hasWiki": has_wiki
            })
        wikis.sort(key=lambda w: w["name"].lower())
        return {"ok": True, "wikis": wikis}
