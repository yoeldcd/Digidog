"""Reference-only vector indexing and hydration for picture descriptions."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib

from brain.infrastructure.pictures.repository import PictureRepository
from brain.application.pictures.config import load_pictures_config
from brain.infrastructure.pictures.knowledge_graph import project_picture_descriptions
from brain.infrastructure.pictures.scanner import scan_pictures
from brain.infrastructure.runtime.paths import get_vectorstore_dir
from brain.infrastructure.vectorstores.manager import VectorStoreManager


PICTURE_VECTOR_COLLECTION = "pictures"


def sync_picture_vectors(db_path: Path | None = None, reset: bool = False) -> dict[str, Any]:
    """Synchronize picture search text while storing only SQLite references."""
    scan_stats = scan_pictures()
    repository = PictureRepository()
    graph_stats = project_picture_descriptions(
        records=repository.list(),
        guidance=load_pictures_config().guidance,
    )
    manager = VectorStoreManager(
        db_path=db_path or get_vectorstore_dir(scope="global"),
        collection_name=PICTURE_VECTOR_COLLECTION,
    )
    try:
        entries_deleted = manager.count_records() if reset else 0
        if reset:
            manager.reset_store()
        current = manager.collection.get(include=["metadatas"])
        existing_ids = {str(metadata.get("picture_id") or "") for metadata in (current.get("metadatas") or [])}
        active_records = repository.list()
        active_ids = {record.id for record in active_records}
        for stale_id in existing_ids - active_ids:
            manager.delete_record(f"picture:{stale_id}")
            entries_deleted += 1
        entries_created = 0
        for record in active_records:
            search_text = " ".join(
                value for value in (record.filename, record.domain, record.relative_path, record.description) if value
            )
            fingerprint = hashlib.sha256(search_text.encode("utf-8")).hexdigest()
            if record.id in existing_ids and record.vector_fingerprint == fingerprint and not reset:
                continue
            manager.add_record(
                doc_id=f"picture:{record.id}",
                text=search_text,
                metadata={"source_kind": "picture", "picture_id": record.id},
            )
            repository.mark_vector_indexed(picture_id=record.id, fingerprint=fingerprint)
            entries_created += 1
    finally:
        manager.close()
    return {
        "collection": PICTURE_VECTOR_COLLECTION,
        "pictures": len(repository.list()),
        "entries_created": entries_created,
        "entries_deleted": entries_deleted,
        "scan": scan_stats,
        "knowledge_graph": graph_stats,
        "reference_only": True,
    }


def search_picture_vectors(text: str, limit: int) -> list[dict[str, Any]]:
    """Search picture embeddings and hydrate matches from SQLite."""
    manager = VectorStoreManager(collection_name=PICTURE_VECTOR_COLLECTION)
    try:
        matches = manager.search(query=text, limit=limit)
    finally:
        manager.close()
    repository = PictureRepository()
    hydrated: list[dict[str, Any]] = []
    for match in matches:
        picture_id = str((match.get("metadata") or {}).get("picture_id") or "")
        record = repository.get(picture_id=picture_id)
        if record is not None and record.active:
            hydrated.append({**match, "record": record, "text": record.description})
    return hydrated
