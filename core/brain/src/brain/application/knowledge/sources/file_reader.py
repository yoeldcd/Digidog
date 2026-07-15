"""Source file content reader for knowledge ingestion."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path


def read_source_text(path: Path) -> str:
    """
    Read a changed source file for model processing.

    Args:
        path: Source file path.

    Returns:
        str: File content.
    """
    if path.name == "brain_logs.db" and path.parent.name == "database":
        from brain.application.logs.export_service import export_logs_markdown

        workspace_root = path.parents[2]
        return export_logs_markdown(workspace_root=workspace_root)
    return path.read_text(encoding="utf-8", errors="ignore")
