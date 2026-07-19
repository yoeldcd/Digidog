"""Picture registry and description routes for Brain Explorer."""

from __future__ import annotations

from typing import Any

from brain.application.pictures.descriptions import set_picture_description
from brain.infrastructure.pictures.models import PictureRecord
from brain.infrastructure.pictures.repository import PictureRepository
from brain.infrastructure.pictures.scanner import scan_pictures
from brain.infrastructure.runtime.paths import get_pictures_dir
from brain.infrastructure.vectorstores.pictures import sync_picture_vectors


def _picture_payload(record: PictureRecord) -> dict[str, Any]:
    """Return one record plus its validated canonical filesystem path."""
    pictures_root = get_pictures_dir().resolve()
    absolute_path = (pictures_root / record.relative_path).resolve()
    try:
        absolute_path.relative_to(pictures_root)
    except ValueError as exc:
        raise ValueError("Registered picture path escapes the pictures directory.") from exc
    return {**record.as_mapping(), "absolute_path": str(absolute_path)}


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
