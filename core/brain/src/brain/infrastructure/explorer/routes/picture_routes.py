"""Picture registry and description routes for Brain Explorer."""

from __future__ import annotations

from typing import Any

from brain.application.pictures.descriptions import set_picture_description
from brain.infrastructure.pictures.repository import PictureRepository
from brain.infrastructure.pictures.scanner import scan_pictures
from brain.infrastructure.vectorstores.pictures import sync_picture_vectors


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
                "pictures": [record.as_mapping() for record in records],
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
            "data": {"picture": record.as_mapping(), "vectors": vectors},
        }
