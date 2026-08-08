"""Picture registry and description routes for Brain Explorer."""

from __future__ import annotations

from http import HTTPStatus
from io import BytesIO
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from PIL import Image, UnidentifiedImageError

from brain.application.pictures.descriptions import set_picture_description
from brain.infrastructure.explorer.contracts import ApiRouteError
from brain.infrastructure.pictures.models import PictureRecord
from brain.infrastructure.pictures.repository import PictureRepository
from brain.infrastructure.pictures.scanner import DEFAULT_EXTENSIONS, scan_pictures
from brain.infrastructure.runtime.paths import get_pictures_dir, resolve_picture_path
from brain.infrastructure.vectorstores.pictures import sync_picture_vectors


def _picture_payload(record: PictureRecord) -> dict[str, Any]:
    """Return one record plus its validated canonical filesystem path."""
    record_scope = str(getattr(record, "scope", "local") or "local")
    if record_scope == "local":
        legacy_root = get_pictures_dir().resolve()
        absolute_path = (legacy_root / record.relative_path).resolve()
        if not absolute_path.is_file():
            absolute_path = resolve_picture_path(scope=record_scope, relative_path=record.relative_path)
    else:
        absolute_path = resolve_picture_path(scope=record_scope, relative_path=record.relative_path)
    return {**record.as_mapping(), "absolute_path": str(absolute_path)}


MAX_PICTURE_IMPORT_BYTES = 25 * 1024 * 1024
"""Maximum accepted source size for one local picture import."""


class PictureRoutesMixin:
    """Expose canonical picture data through bounded local API contracts."""

    def _pictures(self, query: dict[str, str]) -> dict[str, Any]:
        """Return the domain structure or one lazily requested record scope."""
        truthy = {"1", "true", "yes", "on"}
        structure_only = query.get("structure_only", "").strip().lower() in truthy
        refresh = query.get("refresh", "").strip().lower() in truthy
        scan = scan_pictures() if structure_only or refresh else {}
        repository = PictureRepository()
        domain = query.get("domain", "").strip()
        search = query.get("q", "").strip()
        picture_id = query.get("picture_id", "").strip()
        if structure_only:
            records = []
        elif picture_id:
            record = repository.get(picture_id=picture_id)
            records = [record] if record is not None and record.active else []
        elif search:
            records = repository.search(query=search, domain=domain, limit=500)
        else:
            records = repository.list(domain=domain)
        domains: dict[str, int] = {}
        if structure_only:
            for record in repository.list():
                domains[record.domain] = domains.get(record.domain, 0) + 1
        return {
            "ok": True,
            "command": ["pictures"],
            "code": 0,
            "stdout": "",
            "stderr": "",
            "durationMs": 0,
            "data": {
                "pictures": [_picture_payload(record) for record in records],
                "domains": domains,
                "scan": scan,
            },
        }

    def _import_picture(self, query: dict[str, str]) -> dict[str, Any]:
        """Persist one validated browser-selected image and synchronize its registry record."""
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise ApiRouteError(HTTPStatus.BAD_REQUEST, "Picture data is required.")
        if content_length > MAX_PICTURE_IMPORT_BYTES:
            raise ApiRouteError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Picture import exceeds the 25 MiB limit.")
        source_name = unquote(self.headers.get("X-Picture-Filename", "")).strip()
        filename = Path(source_name).name
        if not filename or filename != source_name or filename in {".", ".."}:
            raise ApiRouteError(HTTPStatus.BAD_REQUEST, "Picture filename is invalid.")
        extension = Path(filename).suffix.casefold()
        if extension not in DEFAULT_EXTENSIONS:
            raise ApiRouteError(HTTPStatus.BAD_REQUEST, f"Unsupported picture type `{extension or 'none'}`.")
        domain = query.get("domain", "").strip()
        if domain and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", domain):
            raise ApiRouteError(HTTPStatus.BAD_REQUEST, "Picture domain is invalid.")
        parts = [part for part in domain.split(".") if part]
        if any(part in {".", ".."} for part in parts):
            raise ApiRouteError(HTTPStatus.BAD_REQUEST, "Picture domain is invalid.")
        image_bytes = self.rfile.read(content_length)
        if len(image_bytes) != content_length:
            raise ApiRouteError(HTTPStatus.BAD_REQUEST, "Picture upload is incomplete.")
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                image.verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise ApiRouteError(HTTPStatus.BAD_REQUEST, "Uploaded file is not a valid image.") from exc
        pictures_root = get_pictures_dir().resolve()
        destination = (pictures_root.joinpath(*parts) / filename).resolve()
        try:
            destination.relative_to(pictures_root)
        except ValueError as exc:
            raise ApiRouteError(HTTPStatus.FORBIDDEN, "Picture destination is unsafe.") from exc
        if destination.exists():
            raise ApiRouteError(HTTPStatus.CONFLICT, "A picture with this name already exists in the target folder.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(image_bytes)
        scan = scan_pictures()
        relative_path = destination.relative_to(pictures_root).as_posix()
        record = PictureRepository().get(relative_path=relative_path)
        if record is None or not record.active:
            raise ApiRouteError(HTTPStatus.INTERNAL_SERVER_ERROR, "Imported picture could not be registered.")
        return {
            "ok": True,
            "command": ["import-picture", relative_path],
            "code": 0,
            "stdout": "",
            "stderr": "",
            "durationMs": 0,
            "data": {"picture": _picture_payload(record), "scan": scan},
        }

    def _describe_picture(self) -> dict[str, Any]:
        """Persist one manual or model-backed description from Explorer."""
        body = self._read_json_body()
        picture_id = str(body.get("pictureId") or "").strip()
        if not picture_id:
            raise ValueError("pictureId is required.")
        record = set_picture_description(
            picture_id=picture_id,
            description=str(body.get("description") or ""),
            prompt=str(body.get("prompt") or ""),
        )
        vectors = sync_picture_vectors()
        return {
            "ok": True,
            "command": ["describe-picture", picture_id],
            "code": 0,
            "stdout": "",
            "stderr": "",
            "durationMs": 0,
            "data": {"picture": _picture_payload(record), "vectors": vectors},
        }
