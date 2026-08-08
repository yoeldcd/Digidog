"""Canonical application service for scoped picture registration."""

from __future__ import annotations

import base64
import binascii
import hashlib
import mimetypes
import os
import re
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from brain.application.pictures.descriptions import set_picture_description
from brain.infrastructure.pictures.models import PictureRecord
from brain.infrastructure.pictures.repository import PictureRepository
from brain.infrastructure.pictures.scanner import DEFAULT_EXTENSIONS, scan_pictures
from brain.infrastructure.runtime.paths import (
    get_picture_root,
    get_pictures_dir,
    normalize_picture_scope,
)


_DOMAIN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*(?:\.[A-Za-z0-9][A-Za-z0-9_-]*)*$")
_FORMAT_EXTENSIONS = {
    "BMP": ".bmp",
    "GIF": ".gif",
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}


@dataclass(frozen=True, slots=True)
class _ImagePayload:
    """Validated image bytes and the metadata needed for deterministic placement."""

    content: bytes
    filename: str
    mime_type: str
    extension: str
    width: int
    height: int


def register_picture(
    *,
    image_file: str | Path | None = None,
    image_data: str | None = None,
    scope: str,
    domain: str,
    description: str = "",
    repository: PictureRepository | None = None,
    agent_home: Path | None = None,
    core_root: Path | None = None,
    pictures_root: Path | None = None,
    index: bool = False,
) -> PictureRecord:
    """Register one image in a scoped domain and optionally describe it.

    Args:
        image_file: Full path to an existing supported image file.
        image_data: Raw base64 or a MIME-qualified data URL.
        scope: Picture source scope, either local or global.
        domain: Dot-separated domain chain used as nested directories.
        description: Optional manual Markdown description.
        repository: Optional repository override for tests and composition.
        agent_home: Optional local agent-home override.
        core_root: Optional global core-root override.
        pictures_root: Optional explicit destination root.
        index: Whether to refresh picture semantic references after registration.

    Returns:
        PictureRecord: The active registry record after placement and description.

    Raises:
        ValueError: If source, scope, domain, image format, or destination is invalid.
        FileNotFoundError: If image_file does not exist.
    """
    normalized_scope = normalize_picture_scope(scope)
    normalized_domain = _normalize_domain(domain)
    payload = _load_image_payload(image_file=image_file, image_data=image_data)
    registration_root = (
        pictures_root.resolve()
        if pictures_root is not None
        else get_picture_root(
            scope=normalized_scope,
            agent_home=agent_home,
            core_root=core_root,
        )
    )
    scan_root = (
        registration_root
        if pictures_root is not None or normalized_scope == "global"
        else get_pictures_dir(agent_home=agent_home)
    ).resolve()
    registration_root.mkdir(parents=True, exist_ok=True)
    scan_root.mkdir(parents=True, exist_ok=True)
    target_directory = (registration_root / Path(*normalized_domain.split("."))).resolve()
    target_directory.relative_to(registration_root)
    target_directory.mkdir(parents=True, exist_ok=True)

    content_hash = hashlib.sha256(payload.content).hexdigest()
    filename = _safe_filename(payload.filename, payload.extension)
    relative_path = (target_directory / filename).relative_to(scan_root).as_posix()
    target_path = (target_directory / filename).resolve()
    repository = repository or PictureRepository()
    existing = repository.get(relative_path=relative_path, scope=normalized_scope)

    if target_path.exists():
        if not target_path.is_file():
            raise ValueError(f"Picture destination is not a file: {target_path}")
        if _hash_file(target_path) != content_hash:
            raise ValueError(f"Picture destination already contains different content: {relative_path}")
    else:
        _atomic_write(target_path=target_path, content=payload.content)

    scan_pictures(
        repository=repository,
        pictures_root=scan_root,
        scope=normalized_scope,
    )
    record = repository.get(relative_path=relative_path, scope=normalized_scope)
    if record is None:
        raise RuntimeError(f"Registered image was not found after synchronization: {relative_path}")

    normalized_description = description.strip()
    if normalized_description:
        record = repository.update_description(
            picture_id=record.id,
            description=normalized_description,
            source="manual",
            described_at=datetime.now().astimezone().isoformat(),
        )
    elif not record.description.strip():
        record = set_picture_description(
            picture_id=record.id,
            repository=repository,
            pictures_root=scan_root,
        )
    if index:
        from brain.infrastructure.vectorstores.pictures import sync_picture_vectors

        sync_picture_vectors()
    return record


def _normalize_domain(domain: str) -> str:
    """Validate and normalize the dotted domain chain used for placement."""
    normalized_domain = str(domain).strip().strip(".")
    if not normalized_domain or not _DOMAIN_PATTERN.fullmatch(normalized_domain):
        raise ValueError(
            "Domain must be a dotted chain of safe labels such as a.b.c; "
            "path separators and parent traversal are not allowed."
        )
    return normalized_domain


def _load_image_payload(
    *,
    image_file: str | Path | None,
    image_data: str | None,
) -> _ImagePayload:
    """Load exactly one source and validate its raster before writing."""
    has_file = image_file is not None and str(image_file).strip()
    has_data = image_data is not None and str(image_data).strip()
    if bool(has_file) == bool(has_data):
        raise ValueError("Provide exactly one of image_file or image_data.")
    if has_file:
        source_path = Path(str(image_file)).expanduser().resolve()
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        extension = source_path.suffix.casefold()
        if extension not in DEFAULT_EXTENSIONS:
            raise ValueError(f"Unsupported picture extension: {extension or '<none>'}")
        payload = source_path.read_bytes()
        image = _inspect_image(payload)
        compatible_extensions = {extension}
        if extension == ".jpeg":
            compatible_extensions.add(".jpg")
        if image.extension not in compatible_extensions:
            raise ValueError(
                f"Image format {image.extension} does not match file extension {extension}."
            )
        return _ImagePayload(
            content=payload,
            filename=source_path.name,
            mime_type=mimetypes.guess_type(source_path.name)[0] or image.mime_type,
            extension=extension,
            width=image.width,
            height=image.height,
        )

    encoded = str(image_data).strip()
    mime_type = ""
    if encoded.casefold().startswith("data:"):
        header, separator, encoded = encoded.partition(",")
        if not separator or ";base64" not in header.casefold():
            raise ValueError("image_data must be raw base64 or a base64 data URL.")
        mime_type = header[5:].split(";", 1)[0].strip().casefold()
    encoded = "".join(encoded.split())
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("image_data is not valid base64.") from exc
    image = _inspect_image(payload)
    filename = f"image-{hashlib.sha256(payload).hexdigest()[:16]}{image.extension}"
    return _ImagePayload(
        content=payload,
        filename=filename,
        mime_type=mime_type or image.mime_type,
        extension=image.extension,
        width=image.width,
        height=image.height,
    )


def _inspect_image(content: bytes) -> _ImagePayload:
    """Verify image bytes and return detected format metadata."""
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            image_format = str(image.format or "").upper()
            extension = _FORMAT_EXTENSIONS.get(image_format, "")
            if extension not in DEFAULT_EXTENSIONS:
                raise ValueError(f"Unsupported image format: {image_format or '<unknown>'}")
            return _ImagePayload(
                content=content,
                filename="",
                mime_type=Image.MIME.get(image_format, "application/octet-stream"),
                extension=extension,
                width=int(image.width),
                height=int(image.height),
            )
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Image content is not a supported, readable raster.") from exc


def _safe_filename(filename: str, extension: str) -> str:
    """Keep the source basename and reject path traversal or extension changes."""
    safe_name = Path(filename).name
    if not safe_name or safe_name in {".", ".."}:
        raise ValueError("Image filename is empty.")
    if Path(safe_name).suffix.casefold() != extension:
        raise ValueError("Image filename extension is inconsistent with its content.")
    return safe_name


def _atomic_write(*, target_path: Path, content: bytes) -> None:
    """Write validated image bytes atomically beside their final destination."""
    temporary_path = target_path.with_name(f".{target_path.name}.{uuid4().hex}.tmp")
    try:
        temporary_path.write_bytes(content)
        os.replace(temporary_path, target_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _hash_file(path: Path) -> str:
    """Return a streaming SHA-256 digest for an existing image."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
