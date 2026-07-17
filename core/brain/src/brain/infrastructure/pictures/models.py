"""Data transfer records for registered pictures."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class PictureRecord:
    """Canonical metadata and description for one image file."""

    id: str
    relative_path: str
    domain: str
    filename: str
    extension: str
    mime_type: str
    size_bytes: int
    mtime_ns: int
    content_hash: str
    width: int
    height: int
    description: str
    description_source: str
    described_at: str
    vector_fingerprint: str
    active: bool
    created_at: str
    updated_at: str

    def as_mapping(self) -> dict[str, Any]:
        """Return a JSON-ready representation of this record."""
        return asdict(self)
