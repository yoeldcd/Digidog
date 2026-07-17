# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Atomic lifecycle operations for global vectorstore generations."""

from __future__ import annotations

# Standard Libraries Imports
import os
import shutil
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

# Third-party Libraries Imports
import chromadb


GenerationBuilder = Callable[[Path], dict[str, Any]]
GenerationValidator = Callable[[Path], dict[str, Any]]


def replace_vectorstore_generation(
    active_path: Path,
    builder: GenerationBuilder,
    validator: GenerationValidator,
) -> dict[str, Any]:
    """Build, validate, and atomically replace one vectorstore directory.

    The prior directory remains available as a rollback generation until the
    new directory is installed and the retired generation can be removed.
    """
    active: Path = active_path.resolve()
    parent: Path = active.parent
    generation_id: str = uuid4().hex
    building: Path = parent / f".{active.name}.building-{generation_id}"
    retired: Path = parent / f".{active.name}.retired-{generation_id}"
    failed_new: Path = parent / f".{active.name}.failed-{generation_id}"
    parent.mkdir(parents=True, exist_ok=True)

    try:
        build_stats: dict[str, Any] = builder(building)
        validation: dict[str, Any] = validator(building)
    except Exception:
        _remove_generation(path=building, parent=parent)
        raise

    had_active: bool = active.exists()
    if had_active:
        os.replace(active, retired)
    try:
        os.replace(building, active)
    except Exception:
        if had_active and retired.exists():
            os.replace(retired, active)
        _remove_generation(path=building, parent=parent)
        raise

    try:
        if retired.exists():
            _remove_generation(path=retired, parent=parent)
    except Exception:
        os.replace(active, failed_new)
        if had_active and retired.exists():
            os.replace(retired, active)
        _remove_generation(path=failed_new, parent=parent)
        raise

    return {
        "active_path": active.as_posix(),
        "generation_id": generation_id,
        "replaced_existing": had_active,
        "build": build_stats,
        "validation": validation,
    }


def validate_vectorstore_generation(
    generation_path: Path,
    expected_collections: set[str],
) -> dict[str, Any]:
    """Validate that a closed generation contains exactly the expected collections."""
    client = chromadb.PersistentClient(path=str(generation_path))
    try:
        collections = client.list_collections()
        counts: dict[str, int] = {collection.name: int(collection.count()) for collection in collections}
    finally:
        close_client = getattr(client, "close", None)
        if callable(close_client):
            close_client()
    actual_collections: set[str] = set(counts)
    if actual_collections != expected_collections:
        raise RuntimeError(
            "Vectorstore generation collections mismatch: "
            f"expected {sorted(expected_collections)}, found {sorted(actual_collections)}"
        )
    if counts.get("memories", 0) <= 0:
        raise RuntimeError("Vectorstore generation contains no memory vectors.")
    return {
        "collections": counts,
        "total_vectors": sum(counts.values()),
    }


def _remove_generation(path: Path, parent: Path) -> None:
    """Remove one verified sibling generation directory."""
    resolved_path: Path = path.resolve()
    resolved_parent: Path = parent.resolve()
    if resolved_path.parent != resolved_parent:
        raise RuntimeError(f"Refusing to remove vectorstore path outside {resolved_parent}: {resolved_path}")
    if resolved_path.is_dir():
        shutil.rmtree(resolved_path)
    elif resolved_path.exists():
        resolved_path.unlink()
