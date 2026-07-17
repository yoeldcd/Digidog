# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Reference-only vector indexing for workspace avatar messages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from brain.infrastructure.messages.repository import MessageRepository, message_database_path
from brain.infrastructure.runtime.paths import get_brain_mirrors_path, get_vectorstore_dir
from brain.infrastructure.vectorstores.manager import VectorStoreManager


MESSAGE_VECTOR_COLLECTION = "messages"
"""Global collection containing message embeddings and SQLite references."""


def sync_all_message_vectors(
    db_path: Path | None = None,
    *,
    reset: bool = False,
) -> dict[str, Any]:
    """Synchronize registered consumer messages without copying their text."""
    vectorstore_path: Path = db_path or get_vectorstore_dir(scope="global")
    manager = VectorStoreManager(db_path=vectorstore_path, collection_name=MESSAGE_VECTOR_COLLECTION)
    try:
        entries_deleted: int = manager.count_records() if reset else 0
        if reset:
            manager.reset_store()

        existing = manager.collection.get(include=["metadatas"])
        existing_references: set[tuple[str, str]] = {
            (str(meta.get("consumer_path") or ""), str(meta.get("message_id") or ""))
            for meta in (existing.get("metadatas") or [])
            if meta
        }
        entries_created: int = 0
        consumers_indexed: int = 0
        for consumer_path in registered_consumer_paths():
            database_path: Path = message_database_path(consumer_path=consumer_path, require_registered=False)
            if not database_path.is_file():
                continue
            repository = MessageRepository(consumer_path=consumer_path, require_registered=False)
            consumer_key: str = consumer_path.as_posix()
            offset: int = 0
            consumer_had_records: bool = False
            while True:
                records = repository.list_messages(limit=500, offset=offset)
                if not records:
                    break
                consumer_had_records = True
                for record in records:
                    reference = (consumer_key, record.id)
                    if reference in existing_references:
                        continue
                    manager.add_record(
                        doc_id=message_vector_id(consumer_path=consumer_path, message_id=record.id),
                        text=record.text,
                        metadata={
                            "source_kind": "message",
                            "consumer_path": consumer_key,
                            "message_id": record.id,
                        },
                    )
                    existing_references.add(reference)
                    entries_created += 1
                offset += len(records)
            if consumer_had_records:
                consumers_indexed += 1
    finally:
        close_manager = getattr(manager, "close", None)
        if callable(close_manager):
            close_manager()
    return {
        "collection": MESSAGE_VECTOR_COLLECTION,
        "consumers_indexed": consumers_indexed,
        "entries_created": entries_created,
        "entries_deleted": entries_deleted,
        "reference_only": True,
    }


def search_message_vectors(consumer_path: Path, text: str, limit: int) -> list[dict[str, Any]]:
    """Search message embeddings and hydrate matches from the canonical database."""
    resolved_consumer: Path = consumer_path.resolve()
    manager = VectorStoreManager(collection_name=MESSAGE_VECTOR_COLLECTION)
    try:
        matches = manager.search(
            query=text,
            limit=limit,
            where_filter={"consumer_path": resolved_consumer.as_posix()},
        )
    finally:
        close_manager = getattr(manager, "close", None)
        if callable(close_manager):
            close_manager()
    repository = MessageRepository(consumer_path=resolved_consumer, require_registered=False)
    hydrated: list[dict[str, Any]] = []
    for match in matches:
        metadata: dict[str, Any] = dict(match.get("metadata") or {})
        record = repository.get_message(str(metadata.get("message_id") or ""))
        if record is None:
            continue
        hydrated.append({**match, "text": record.text, "record": record})
    return hydrated


def registered_consumer_paths() -> list[Path]:
    """Return canonical consumer paths declared by the core mirror registry."""
    try:
        payload = json.loads(get_brain_mirrors_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [
        Path(str(item.get("path") or "")).expanduser().resolve()
        for item in payload
        if isinstance(item, dict) and str(item.get("path") or "").strip()
    ]


def message_vector_id(consumer_path: Path, message_id: str) -> str:
    """Return a stable ID without duplicating the message body."""
    consumer_hash: str = hashlib.sha256(consumer_path.as_posix().casefold().encode("utf-8")).hexdigest()[:16]
    return f"message:{consumer_hash}:{message_id}"
