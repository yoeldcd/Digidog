"""Workspace log vector indexing and search helpers."""

from __future__ import annotations

# Standard Libraries Imports
import datetime
import os
import re
import time
from pathlib import Path
from typing import Protocol

# Application Modules Imports
from brain.infrastructure.vectorstores.chunking import log_entry_body_text, normalized_entry_time, reader_command_for_entry


class LogVectorManagerProtocol(Protocol):
    """Protocol for manager methods used by log vector helpers."""

    def delete_by_metadata(self, filter_dict: dict) -> int:
        """Delete records matching `filter_dict`."""

    def add_record(self, doc_id: str, text: str, metadata: dict, embedding: list[float] | None = None) -> None:
        """Add or replace a vector record."""

    def search(self, query: str, limit: int = 5, where_filter: dict | None = None) -> list[dict]:
        """Search vector records."""


def index_log_file(manager: LogVectorManagerProtocol, file_path: Path) -> dict[str, int | str]:
    """Parse and index all entries inside a standard `.log.md` file."""
    from brain.application.logs.parsing import is_canonical_log_file, parse_entry, parse_log_timestamp

    from brain.infrastructure.runtime.paths import get_workspace_root

    workspace_root = get_workspace_root()
    logs_dir = workspace_root / "$agent" / "logs"

    if not file_path.exists() or not is_canonical_log_file(file_path):
        return {"path": file_path.as_posix(), "entries_created": 0, "entries_deleted": 0}

    rel_path = file_path.relative_to(logs_dir).as_posix()
    deleted_count = manager.delete_by_metadata({"path": rel_path})

    content = file_path.read_text(encoding="utf-8")
    if "## " not in content:
        return {"path": rel_path, "entries_created": 0, "entries_deleted": deleted_count}

    parse_content = content if content.startswith("\n") else f"\n{content}"
    _, *entry_parts = parse_content.split("\n## ")
    created_count = 0

    for part in entry_parts:
        part_clean = re.split(r"\n\s*---\s*$", part, flags=re.MULTILINE)[0].strip()
        lines = part_clean.splitlines()
        if not lines:
            continue
        entry_ts = lines[0].strip()
        body_text = "\n".join(lines[1:])

        domain, title, git_type = parse_entry(entry_ts, body_text)
        if domain == "domain[.subdomain]" or entry_ts.startswith("DD-MM-YYYY"):
            continue

        parsed_dt = parse_log_timestamp(entry_ts)
        timestamp_sec = parsed_dt.timestamp() if parsed_dt != datetime.datetime.min else 0.0

        entry_time = normalized_entry_time(entry_ts)
        read_command = reader_command_for_entry(command_name="read-log", date_text=entry_ts[:10], entry_time=entry_time)
        doc_text = log_entry_body_text(body_text=body_text)
        if not doc_text:
            continue

        ts_slug = re.sub(r"[^a-zA-Z0-9]", "-", entry_ts).strip("-")
        chunk_id = f"log.{rel_path}#{ts_slug}"

        metadata = {
            "path": rel_path,
            "source_kind": "log",
            "domain": domain,
            "title": title,
            "entry_title": title,
            "entry_time": entry_time,
            "read_command": read_command,
            "body": doc_text,
            "type": git_type,
            "timestamp": entry_ts,
            "timestamp_sec": timestamp_sec,
            "mtime": file_path.stat().st_mtime,
        }
        manager.add_record(chunk_id, doc_text, metadata)
        created_count += 1
    return {
        "path": rel_path,
        "entries_created": created_count,
        "entries_deleted": deleted_count,
    }


def index_log_entries(manager: LogVectorManagerProtocol, entries: list[object]) -> dict[str, int | str]:
    """Index DB-backed log records into the local logs collection."""
    from brain.application.logs.parsing import parse_log_timestamp

    deleted_count = manager.delete_by_metadata({"source_kind": "log"})
    created_count = 0
    for entry in entries:
        entry_ts = str(getattr(entry, "timestamp", ""))
        domain = str(getattr(entry, "domain", "unknown"))
        title = str(getattr(entry, "title", ""))
        git_type = str(getattr(entry, "change_type", ""))
        source_path = str(getattr(entry, "source_path", "") or "")
        rel_path = source_path.replace("$agent/logs/", "", 1) if source_path else "database/brain_logs.db"
        doc_text = log_record_text(entry=entry)
        if not doc_text:
            continue

        parsed_dt = parse_log_timestamp(entry_ts)
        timestamp_sec = parsed_dt.timestamp() if parsed_dt != datetime.datetime.min else 0.0
        entry_time = normalized_entry_time(entry_ts)
        read_command = reader_command_for_entry(command_name="read-log", date_text=entry_ts[:10], entry_time=entry_time)
        chunk_id = f"log.db#{_log_record_slug(entry_ts=entry_ts, domain=domain, title=title)}"
        metadata = {
            "path": rel_path,
            "source_kind": "log",
            "source_backend": "sqlite",
            "domain": domain,
            "title": title,
            "entry_title": title,
            "entry_time": entry_time,
            "read_command": read_command,
            "body": doc_text,
            "type": git_type,
            "timestamp": entry_ts,
            "timestamp_sec": timestamp_sec,
            "mtime": float(getattr(entry, "source_mtime", 0.0) or 0.0),
        }
        manager.add_record(chunk_id, doc_text, metadata)
        created_count += 1
    return {
        "path": "database/brain_logs.db",
        "entries_created": created_count,
        "entries_deleted": deleted_count,
    }


def log_record_text(entry: object) -> str:
    """Build searchable text for one DB-backed log record."""
    parts = [
        str(getattr(entry, "domain", "")),
        str(getattr(entry, "title", "")),
        str(getattr(entry, "change_type", "")),
        str(getattr(entry, "why", "")),
        str(getattr(entry, "description", "")),
        str(getattr(entry, "impact", "")),
    ]
    return "\n".join(part.strip() for part in parts if part and part.strip())


def _log_record_slug(entry_ts: str, domain: str, title: str) -> str:
    """Return a stable vector id suffix for one log record."""
    raw_slug = f"{entry_ts}-{domain}-{title}"
    return re.sub(r"[^a-zA-Z0-9]", "-", raw_slug).strip("-")


def search_logs(
    manager: LogVectorManagerProtocol,
    query: str,
    domain_filter: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Perform semantic search on logs with optional domain filtering and recency decay."""
    raw_limit = limit * 4 if domain_filter else limit * 2
    results = manager.search(query, limit=raw_limit)

    formatted = []
    now_sec = time.time()

    for result in results:
        meta = result["metadata"]
        log_domain = meta.get("domain", "unknown")

        if domain_filter:
            if not (log_domain == domain_filter or log_domain.startswith(f"{domain_filter}.")):
                continue

        similarity = result["similarity"]
        timestamp_sec = meta.get("timestamp_sec", 0.0)

        age_days = max(0.0, (now_sec - timestamp_sec) / (24 * 3600))
        recency_factor = 1.0 / (1.0 + 0.01 * age_days)
        combined_score = similarity * recency_factor

        formatted.append({
            "id": result["id"],
            "text": result["text"],
            "path": meta.get("path"),
            "domain": log_domain,
            "title": meta.get("title"),
            "type": meta.get("type"),
            "timestamp": meta.get("timestamp"),
            "read_command": meta.get("read_command", ""),
            "similarity": similarity,
            "recency_factor": recency_factor,
            "score": combined_score,
        })

    formatted.sort(key=lambda item: item["score"], reverse=True)
    return formatted[:limit]
