"""Own persistence and validation for always-on workspace records.

Records are independent from Markdown memory entries. The service owns the
canonical ``$agent/data/records.json`` contract; policy-oriented CLI spellings
are aliases in presentation metadata and do not alter this storage identity.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from brain.application.memory.paths import write_text_atomic
from brain.infrastructure.runtime.paths import get_workspace_root

_RECORD_ID_PATTERN = re.compile(r"rec(\d+)$")


@dataclass(frozen=True, slots=True)
class LiveRecord:
    """Represent one validated always-on record.

    Attributes:
        id: Stable public identifier in ``rec##`` format.
        text: Non-empty context content injected into supported operations.
        created_at: ISO-8601 UTC creation timestamp.
    """

    id: str
    text: str
    created_at: str


def records_path(workspace_root: Path | None = None) -> Path:
    """Resolve the canonical workspace-local records document.

    Args:
        workspace_root: Optional workspace override used by isolated callers and
            tests. The active workspace is used when omitted.

    Returns:
        Absolute path to ``$agent/data/records.json``.
    """
    return get_workspace_root(workspace_root) / "$agent" / "data" / "records.json"


def list_live_records(workspace_root: Path | None = None) -> list[LiveRecord]:
    """Return all validated records in stable creation order.

    Args:
        workspace_root: Optional workspace override.

    Returns:
        Materialized record objects; an absent store produces an empty list.

    Raises:
        ValueError: The persisted JSON or any record violates its contract.
    """
    payload = _read_live_records_payload(workspace_root=workspace_root)
    return [LiveRecord(**item) for item in payload["records"]]


def read_live_record(record_id: str, workspace_root: Path | None = None) -> LiveRecord:
    """Read one record by its public identifier.

    Args:
        record_id: Identifier in ``rec##`` format.
        workspace_root: Optional workspace override.

    Returns:
        The matching validated record.

    Raises:
        ValueError: The identifier is invalid or no active record matches it.
    """
    normalized_id = _normalize_live_record_id(record_id)
    for record in list_live_records(workspace_root=workspace_root):
        if record.id == normalized_id:
            return record
    raise ValueError(f"Live record '{normalized_id}' does not exist.")


def add_live_record(text: str, workspace_root: Path | None = None) -> LiveRecord:
    """Append one record and reserve the next monotonic identifier.

    Args:
        text: Non-empty record content.
        workspace_root: Optional workspace override.

    Returns:
        The persisted record with its assigned ID and timestamp.

    Raises:
        ValueError: Content is empty or existing persisted data is invalid.
    """
    normalized_text = text.strip()
    if not normalized_text:
        raise ValueError("Live record text cannot be empty.")
    payload = _read_live_records_payload(workspace_root=workspace_root)
    next_number = int(payload["nextId"])
    record = LiveRecord(
        id=f"rec{next_number:02d}",
        text=normalized_text,
        created_at=datetime.now(UTC).isoformat(),
    )
    payload["records"].append(asdict(record))
    payload["nextId"] = next_number + 1
    _write_live_records_payload(payload=payload, workspace_root=workspace_root)
    return record


def delete_live_record(record_id: str, workspace_root: Path | None = None) -> LiveRecord:
    """Delete one record without reusing its monotonic identifier.

    Args:
        record_id: Identifier in ``rec##`` format.
        workspace_root: Optional workspace override.

    Returns:
        The deleted record.

    Raises:
        ValueError: The identifier is invalid, unknown, or stored data is invalid.
    """
    normalized_id = _normalize_live_record_id(record_id)
    payload = _read_live_records_payload(workspace_root=workspace_root)
    records = payload["records"]
    for index, item in enumerate(records):
        if item["id"] == normalized_id:
            deleted = LiveRecord(**records.pop(index))
            _write_live_records_payload(payload=payload, workspace_root=workspace_root)
            return deleted
    raise ValueError(f"Live record '{normalized_id}' does not exist.")


def _read_live_records_payload(workspace_root: Path | None = None) -> dict[str, object]:
    """Load, normalize, and validate the canonical persistence envelope.

    Args:
        workspace_root: Optional workspace override.

    Returns:
        A dictionary containing monotonic ``nextId`` and ordered ``records``.

    Raises:
        ValueError: JSON shape, IDs, text, or timestamps are invalid.
    """
    path = records_path(workspace_root=workspace_root)
    if not path.is_file():
        return {"nextId": 1, "records": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Live records file is invalid JSON: {path}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValueError("Live records file must contain a records array.")
    records: list[dict[str, str]] = []
    highest_id = 0
    for item in payload["records"]:
        if not isinstance(item, dict):
            raise ValueError("Live records must be JSON objects.")
        record_id = _normalize_live_record_id(str(item.get("id", "")))
        text = str(item.get("text", "")).strip()
        created_at = str(item.get("created_at", "")).strip()
        if not text or not created_at:
            raise ValueError(f"Live record '{record_id}' is missing text or created_at.")
        records.append({"id": record_id, "text": text, "created_at": created_at})
        highest_id = max(highest_id, int(_RECORD_ID_PATTERN.fullmatch(record_id).group(1)))
    next_id = payload.get("nextId", highest_id + 1)
    if not isinstance(next_id, int) or next_id <= highest_id:
        next_id = highest_id + 1
    return {"nextId": next_id, "records": records}


def _write_live_records_payload(payload: dict[str, object], workspace_root: Path | None = None) -> None:
    """Persist a validated records envelope atomically.

    Args:
        payload: Canonical dictionary produced by this service.
        workspace_root: Optional workspace override.
    """
    path = records_path(workspace_root=workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _normalize_live_record_id(record_id: str) -> str:
    """Normalize and validate a public record identifier.

    Args:
        record_id: Candidate identifier.

    Returns:
        Lowercase validated identifier.

    Raises:
        ValueError: The candidate does not match ``rec##``.
    """
    normalized_id = record_id.strip().lower()
    if not _RECORD_ID_PATTERN.fullmatch(normalized_id):
        raise ValueError("Live record ID must use the rec## format, for example rec01.")
    return normalized_id
