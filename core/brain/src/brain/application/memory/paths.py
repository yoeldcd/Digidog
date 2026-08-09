"""Filesystem primitives for the Markdown memory store."""

from __future__ import annotations

import tempfile
from pathlib import Path

# Application Modules Imports
from brain.config import MEMORY_DIR_NAME, TMP_DIR_NAME
from brain.infrastructure.runtime.paths import get_agent_home


AGENT_HOME = get_agent_home()
"""Shared application home directory resolved for memory operations."""

MEMORY_ROOT = AGENT_HOME / MEMORY_DIR_NAME
"""Root directory for Markdown memory domains."""

TMP_DIR = AGENT_HOME / TMP_DIR_NAME
"""Temporary directory used for atomic writes."""


class BrainStoreError(RuntimeError):
    """Raised when the memory store cannot complete a requested operation."""


def validate_part_name(name: str) -> str:
    """Validate a category or key path component.

    Args:
        name (str): Raw component to normalize and validate.

    Returns:
        str: Stripped component containing only supported characters.

    Raises:
        BrainStoreError: The component is empty or contains unsupported characters.
    """
    normalized = name.strip()
    if not normalized:
        raise BrainStoreError("Name components cannot be empty.")
    if not all(char.isalnum() or char in "_-" for char in normalized):
        raise BrainStoreError(
            f"Invalid name component '{normalized}': may only contain alphanumeric characters, underscores, or dashes.",
        )
    return normalized


def resolve_category_dir(category: str) -> Path:
    """Resolve a dot-separated category beneath the memory root.

    Args:
        category (str): Dot-separated memory category.

    Returns:
        Path: Validated category directory beneath the memory root.

    Raises:
        BrainStoreError: The category is empty or contains an invalid component.
    """
    parts = [part.strip() for part in category.split(".") if part.strip()]
    if not parts:
        raise BrainStoreError("Category name cannot be empty.")

    validated_parts = [validate_part_name(part) for part in parts]
    return MEMORY_ROOT.joinpath(*validated_parts)


def resolve_file_path(category: str, key: str) -> Path:
    """Resolve the Markdown path for a category and key.

    Args:
        category (str): Dot-separated memory category.
        key (str): Entry key used as the filename stem.

    Returns:
        Path: Validated Markdown entry path.
    """
    dir_path = resolve_category_dir(category)
    validated_key = validate_part_name(key)
    return dir_path / f"{validated_key}.md"


def ensure_memory_root() -> None:
    """Create the memory root directory if it does not exist."""
    MEMORY_ROOT.mkdir(parents=True, exist_ok=True)


def write_text_atomic(path: Path, content: str) -> None:
    """Write text through an atomic replacement staged in the managed temp directory.

    Args:
        path (Path): Final destination path.
        content (str): UTF-8 text to persist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=TMP_DIR, delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    temp_path.replace(path)
