"""Data transfer records for registered pictures."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class PictureRecord:
    """Canonical metadata and description for one image file.

    Attributes:
        id (str): Stable picture identifier.
        relative_path (str): Path relative to the configured picture root.
        domain (str): Dot-separated directory domain.
        filename (str): Source filename.
        extension (str): Normalized file extension.
        mime_type (str): Detected image media type.
        size_bytes (int): Source size in bytes.
        mtime_ns (int): Source modification timestamp in nanoseconds.
        content_hash (str): Hash of the source bytes.
        width (int): Image width in pixels.
        height (int): Image height in pixels.
        description (str): Canonical textual description.
        description_source (str): Origin of the description.
        described_at (str): Description timestamp.
        vector_fingerprint (str): Fingerprint of indexed search text.
        active (bool): Whether the file exists in the latest scan.
        created_at (str): Record creation timestamp.
        updated_at (str): Record update timestamp.
        scope (str): Picture source scope, either local or global.
    """

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
    scope: str = "local"

    def as_mapping(self) -> dict[str, Any]:
        """Return a JSON-ready representation of this record.

        Returns:
            dict[str, Any]: Canonical record fields for API serialization.
        """
        return asdict(self)
