"""Incrementally synchronize the agent picture tree into SQLite."""

from __future__ import annotations

import hashlib
import mimetypes
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from brain.infrastructure.pictures.models import PictureRecord
from brain.infrastructure.pictures.repository import PictureRepository
from brain.infrastructure.runtime.paths import get_picture_root, get_pictures_dir, normalize_picture_scope


DEFAULT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
PictureScanEvent = Callable[[str, str], None]
"""Callback receiving one scan state and its concrete picture reference."""


def scan_pictures(
    repository: PictureRepository | None = None,
    pictures_root: Path | None = None,
    extensions: set[str] | None = None,
    on_event: PictureScanEvent | None = None,
    scope: str = "local",
) -> dict[str, object]:
    """Synchronize picture files while preserving descriptions and recognizing moves.

    Args:
        repository (PictureRepository | None): Optional picture repository override.
        pictures_root (Path | None): Optional filesystem picture root.
        extensions (set[str] | None): Optional allowed extension override.
        on_event (PictureScanEvent | None): Optional per-file scan event callback.
        scope (str): Picture source scope used for registry isolation.

    Returns:
        dict[str, object]: Scan totals, active records, moves, removals, and errors.
    """
    repo = repository or PictureRepository()
    normalized_scope = normalize_picture_scope(scope)
    default_root = get_pictures_dir() if normalized_scope == "local" else get_picture_root(scope=normalized_scope)
    root = (pictures_root or default_root).resolve()
    supported = {value.casefold() for value in (extensions or DEFAULT_EXTENSIONS)}
    now = datetime.now().astimezone().isoformat()
    files = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.casefold() in supported)
    current_paths = {path.relative_to(root).as_posix() for path in files}
    summary: dict[str, object] = {"added": 0, "changed": 0, "moved": 0, "unchanged": 0, "deleted": 0, "errors": [], "scope": normalized_scope}

    for path in files:
        relative_path = path.relative_to(root).as_posix()
        stat = path.stat()
        existing = repo.get(relative_path=relative_path, scope=normalized_scope)
        if existing and existing.mtime_ns == stat.st_mtime_ns and existing.size_bytes == stat.st_size and existing.active:
            summary["unchanged"] = int(summary["unchanged"]) + 1
            if on_event is not None:
                on_event("unchanged", relative_path)
            continue
        try:
            content_hash = _hash_file(path)
            width, height = _dimensions(path)
        except (OSError, UnidentifiedImageError) as exc:
            errors = summary["errors"]
            assert isinstance(errors, list)
            errors.append({"path": relative_path, "error": str(exc)})
            if on_event is not None:
                on_event("error", relative_path)
            continue

        moved = None if existing else repo.find_active_by_hash(
            content_hash=content_hash,
            excluded_paths=current_paths,
            scope=normalized_scope,
        )
        prior = existing or moved
        model_description_stale = bool(
            prior
            and prior.content_hash != content_hash
            and prior.description_source == "image_model"
        )
        description = "" if model_description_stale else prior.description if prior else ""
        description_source = "" if model_description_stale else prior.description_source if prior else ""
        described_at = "" if model_description_stale else prior.described_at if prior else ""
        vector_fingerprint = (
            prior.vector_fingerprint
            if prior and prior.relative_path == relative_path and not model_description_stale
            else ""
        )
        picture_id = (
            prior.id
            if prior
            else hashlib.sha256(f"{normalized_scope}:{relative_path}".encode("utf-8")).hexdigest()[:24]
        )
        domain_path = Path(relative_path).parent
        if normalized_scope == "local" and domain_path.parts[:1] == ("images",):
            domain_path = Path(*domain_path.parts[1:]) if len(domain_path.parts) > 1 else Path(".")
        domain = ".".join(domain_path.parts) if domain_path != Path(".") else "root"
        record = PictureRecord(
            id=picture_id,
            scope=normalized_scope,
            relative_path=relative_path,
            domain=domain,
            filename=path.name,
            extension=path.suffix.casefold(),
            mime_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            size_bytes=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
            content_hash=content_hash,
            width=width,
            height=height,
            description=description,
            description_source=description_source,
            described_at=described_at,
            vector_fingerprint=vector_fingerprint,
            active=True,
            created_at=prior.created_at if prior else now,
            updated_at=now,
        )
        repo.upsert(record)
        key = "moved" if moved else "changed" if existing else "added"
        summary[key] = int(summary[key]) + 1
        if on_event is not None:
            on_event(key, relative_path)

    missing_ids = repo.deactivate_missing(
        active_paths=current_paths,
        updated_at=now,
        scope=normalized_scope,
    )
    summary["deleted"] = len(missing_ids)
    if on_event is not None:
        for picture_id in missing_ids:
            on_event("deleted", picture_id)
    summary["total"] = len(repo.list(scope=normalized_scope))
    summary["database"] = repo.database_path.as_posix()
    summary["root"] = root.as_posix()
    return summary


def _hash_file(path: Path) -> str:
    """Return a streaming SHA-256 digest for one image."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dimensions(path: Path) -> tuple[int, int]:
    """Read image dimensions without decoding the complete raster."""
    with Image.open(path) as image:
        return int(image.width), int(image.height)
