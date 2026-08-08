# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""SystemRoutesMixin for Brain Explorer."""

from __future__ import annotations

from typing import Any

from brain.infrastructure.explorer.resources import find_documentation_dirs, find_wiki_markdown_files
from brain.infrastructure.explorer.validation import load_registered_projects
from brain.infrastructure.runtime.paths import get_workspace_root


class SystemRoutesMixin:
    """Provide one cohesive group of Explorer routes."""

    def _health_payload(self) -> dict[str, Any]:
        """
        Return server health metadata.

        Returns:
            dict[str, Any]: Health payload.
        """
        workspace_root = get_workspace_root()
        return {
            "ok": True,
            "workspaceRoot": workspace_root.as_posix(),
            "agentHome": (workspace_root / "$agent").as_posix(),
        }

    def _projects_list(self) -> dict[str, Any]:
        """Return the list of registered projects from brain_mirrors.json."""
        return {"ok": True, "projects": load_registered_projects()}

    def _wikis_list(self) -> dict[str, Any]:
        """
        Scan workspace documentation directories and expose live Markdown wikis.
        """
        workspace_root = get_workspace_root()
        doc_dirs = find_documentation_dirs(workspace_root)
        wikis = []
        for d in doc_dirs:
            wiki_name = d.parent.name
            has_wiki = bool(find_wiki_markdown_files(d))
            wikis.append({
                "name": wiki_name,
                "path": d.as_posix(),
                "hasWiki": has_wiki
            })
        wikis.sort(key=lambda w: w["name"].lower())
        return {"ok": True, "workspaceRoot": workspace_root.as_posix(), "wikis": wikis}
