"""Source content access for reviewed knowledge delta workflows."""

from __future__ import annotations

# Standard Libraries Imports
import os
from pathlib import Path

# Application Modules Imports
from brain.infrastructure.runtime.paths import get_agent_home


def read_source_content(row: dict) -> str:
    """
    Read source content for evidence fallback during application.

    Args:
        row (dict): Pending delta row.

    Returns:
        str: Source content when the file is still available.
    """
    source_path_text: str = str(row.get("source_path") or "")
    candidate_paths: list[Path] = [get_agent_home() / source_path_text]
    workspace_root = os.environ.get("WORKSPACE_ROOT")
    if workspace_root:
        candidate_paths.append(Path(workspace_root) / source_path_text)

    for candidate_path in candidate_paths:
        if candidate_path.exists() and candidate_path.is_file():
            return candidate_path.read_text(encoding="utf-8", errors="ignore")
    return ""
