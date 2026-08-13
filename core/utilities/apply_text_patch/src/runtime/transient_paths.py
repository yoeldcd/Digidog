"""Resolve standalone patch transient directories."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Final

CONFIG_DIRECTORY_NAME: Final[str] = "configs"
CONFIG_FILE_NAME: Final[str] = "brain_configs.json"
TRANSIENT_DIRECTORY_KEY: Final[str] = "transient_dir"
AGENT_DIRECTORY_NAME: Final[str] = "$agent"
TEMPORARY_DIRECTORY_NAME: Final[str] = ".tmp"
PATCH_ROLLBACK_DIRECTORY_NAME: Final[str] = "patches_rollback"

def _read_configured_base(config_path: Path) -> Path | None:
    """Read a valid configured transient base directory."""
    if not config_path.is_file():
        return None
    try:
        raw_data: object = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw_data = None
    if not isinstance(raw_data, dict):
        return None
    value = raw_data.get(TRANSIENT_DIRECTORY_KEY)
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value.strip()).expanduser()
    if not candidate.is_absolute() or not candidate.exists() or not candidate.is_dir():
        return None
    return candidate.resolve()


def _create_child_directory(base_directory: Path, child_name: str) -> Path:
    """Create and return a child directory, propagating mkdir failures."""
    child_directory = base_directory / child_name
    child_directory.mkdir(parents=True, exist_ok=True)
    return child_directory


def resolve_transient_dir(workspace_root: Path, core_root: Path) -> Path:
    """Resolve the standalone patch rollback directory."""
    config_path = core_root / CONFIG_DIRECTORY_NAME / CONFIG_FILE_NAME
    configured_base = _read_configured_base(config_path)
    if configured_base is None:
        configured_base = workspace_root.resolve() / AGENT_DIRECTORY_NAME / TEMPORARY_DIRECTORY_NAME
        configured_base.mkdir(parents=True, exist_ok=True)
    return _create_child_directory(configured_base, PATCH_ROLLBACK_DIRECTORY_NAME)