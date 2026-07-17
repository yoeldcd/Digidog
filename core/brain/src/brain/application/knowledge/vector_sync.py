# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Knowledge graph vectorstore synchronization helpers."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path
from typing import Any

# Application Modules Imports
from brain.application.knowledge.runtime.scopes import iter_knowledge_roots
from brain.application.knowledge.runtime.config_store import resolve_secret
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.infrastructure.runtime.paths import get_vectorstore_dir
from brain.infrastructure.vectorstores.embeddings import get_embedding
from brain.infrastructure.vectorstores.manager import VectorStoreManager
from brain.infrastructure.vectorstores.settings import load_config


KNOWLEDGE_VECTOR_COLLECTION = "knowledge"
"""Chroma collection name for knowledge graph vector records."""


def sync_all_knowledge_vectorstores(vectorstore_path: Path | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Synchronize knowledge vectors for all configured graph scopes.

    Returns:
        tuple[list[dict[str, Any]], list[str]]: Sync stats and non-blocking warnings.
    """
    stats: list[dict[str, Any]] = []
    warnings: list[str] = []
    for scope_name, knowledge_root in iter_knowledge_roots(scope="all"):
        repository = KnowledgeRepository(knowledge_root=knowledge_root, scope=scope_name)
        scope_stats, scope_warning = safe_sync_knowledge_vectors(
            repository=repository,
            vectorstore_path=vectorstore_path,
        )
        if scope_stats:
            stats.append(scope_stats)
        if scope_warning:
            warnings.append(scope_warning)
    return stats, warnings


def safe_sync_knowledge_vectors(
    repository: KnowledgeRepository,
    vectorstore_path: Path | None = None,
) -> tuple[dict[str, Any], str]:
    """
    Best-effort sync wrapper that never blocks graph application.

    Args:
        repository (KnowledgeRepository): Knowledge repository.

    Returns:
        tuple[dict[str, Any], str]: Sync stats and warning text.
    """
    try:
        return sync_knowledge_vectors(repository=repository, vectorstore_path=vectorstore_path), ""
    except Exception as exc:
        return {}, f"Knowledge vector sync skipped ({repository.scope}): {exc}"


def sync_knowledge_vectors(
    repository: KnowledgeRepository,
    vectorstore_path: Path | None = None,
) -> dict[str, Any]:
    """
    Rebuild knowledge vectors for one repository scope.

    Args:
        repository (KnowledgeRepository): Knowledge repository.

    Returns:
        dict[str, Any]: Sync statistics.

    Raises:
        RuntimeError: If embeddings are not configured.
    """
    ensure_embedding_config_available()
    manager: VectorStoreManager = (
        VectorStoreManager(db_path=vectorstore_path, collection_name=KNOWLEDGE_VECTOR_COLLECTION)
        if vectorstore_path is not None
        else open_knowledge_vectorstore(scope=repository.scope)
    )
    try:
        removed_count: int = manager.delete_by_metadata({"knowledge_scope": repository.scope})
        indexed_count: int = 0
        for entity_row in repository.list_entities():
            manager.add_record(
                doc_id=knowledge_doc_id(scope=repository.scope, kind="entity", record_id=int(entity_row["id"])),
                text=entity_vector_text(entity_row=entity_row),
                metadata=entity_vector_metadata(scope=repository.scope, entity_row=entity_row),
            )
            indexed_count += 1
        for relation_row in repository.list_relations():
            manager.add_record(
                doc_id=knowledge_doc_id(scope=repository.scope, kind="relation", record_id=int(relation_row["id"])),
                text=relation_vector_text(relation_row=relation_row),
                metadata=relation_vector_metadata(scope=repository.scope, relation_row=relation_row),
            )
            indexed_count += 1
    finally:
        close_manager = getattr(manager, "close", None)
        if callable(close_manager):
            close_manager()
    return {
        "knowledge_scope": repository.scope,
        "entries_created": indexed_count,
        "entries_deleted": removed_count,
    }


def search_knowledge_vectors(repository: KnowledgeRepository, text: str, limit: int) -> list[dict[str, Any]]:
    """
    Search knowledge vector records for one graph scope.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        text (str): Search text.
        limit (int): Maximum result count.

    Returns:
        list[dict[str, Any]]: Vector matches.
    """
    manager: VectorStoreManager = open_knowledge_vectorstore(scope=repository.scope, create=False)
    try:
        matches: list[dict[str, Any]] = manager.search(
            query=text,
            limit=limit,
            where_filter={"knowledge_scope": repository.scope},
        )
    finally:
        close_manager = getattr(manager, "close", None)
        if callable(close_manager):
            close_manager()
    return [
        hydrate_knowledge_vector_match(repository=repository, match=match)
        for match in matches
    ]


def hydrate_knowledge_vector_match(
    repository: KnowledgeRepository,
    match: dict[str, Any],
) -> dict[str, Any]:
    """Hydrate a reference-only knowledge vector from canonical SQLite rows."""
    metadata: dict[str, Any] = dict(match.get("metadata") or {})
    kind: str = str(metadata.get("knowledge_kind") or "")
    record_id: int = int(metadata.get("record_id") or 0)
    if kind == "entity":
        row = repository.get_entity(record_id)
        if row:
            match["text"] = entity_vector_text(entity_row=row)
            match["metadata"] = hydrated_entity_vector_metadata(
                reference_metadata=metadata,
                entity_row=row,
            )
    elif kind == "relation":
        row = next(
            (item for item in repository.list_relations() if int(item.get("id") or 0) == record_id),
            None,
        )
        if row:
            match["text"] = relation_vector_text(relation_row=row)
            match["metadata"] = hydrated_relation_vector_metadata(
                reference_metadata=metadata,
                relation_row=row,
            )
    return match


def hydrated_entity_vector_metadata(
    reference_metadata: dict[str, Any],
    entity_row: dict[str, Any],
) -> dict[str, Any]:
    """Expand an entity reference for query presentation without persisting payload copies."""
    assertions: list[dict[str, Any]] = [
        assertion
        for assertion in entity_row.get("type_assertions", [])
        if isinstance(assertion, dict)
    ]
    source_assertion: dict[str, Any] = assertions[0] if assertions else {}
    return {
        **reference_metadata,
        "entity_id": int(entity_row["id"]),
        "entity_class": str(entity_row.get("entity_class") or ""),
        "entity_name": str(entity_row.get("canonical_name") or ""),
        "entity_description": str(entity_row.get("description") or ""),
        "source_path": str(entity_row.get("source_path") or source_assertion.get("source_path") or ""),
        "source_type": str(entity_row.get("source_type") or source_assertion.get("source_type") or ""),
        "source_title": str(entity_row.get("source_title") or source_assertion.get("source_title") or ""),
    }


def hydrated_relation_vector_metadata(
    reference_metadata: dict[str, Any],
    relation_row: dict[str, Any],
) -> dict[str, Any]:
    """Expand a relation reference for query presentation without persisting payload copies."""
    return {
        **reference_metadata,
        "relation_id": int(relation_row["id"]),
        "predicate": str(relation_row.get("predicate") or ""),
        "subject_id": int(relation_row.get("subject_entity_id") or 0),
        "subject_class": str(relation_row.get("subject_class") or ""),
        "subject_name": str(relation_row.get("subject_name") or ""),
        "object_id": int(relation_row.get("object_entity_id") or 0),
        "object_class": str(relation_row.get("object_class") or ""),
        "object_name": str(relation_row.get("object_name") or ""),
        "source_path": str(relation_row.get("source_path") or ""),
    }


def open_knowledge_vectorstore(scope: str, create: bool = True) -> VectorStoreManager:
    """
    Open the scoped knowledge vectorstore collection.

    Args:
        scope (str): Knowledge scope.
        create (bool): Whether missing vectorstore directories may be created.

    Returns:
        VectorStoreManager: Manager for the knowledge collection.
    """
    if create:
        vectorstore_path: Path = get_vectorstore_dir(scope=scope)
    else:
        vectorstore_path = get_vectorstore_dir(scope=scope, create=False)
        if not vectorstore_path.exists():
            raise RuntimeError("knowledge vectorstore has not been indexed")
    return VectorStoreManager(db_path=vectorstore_path, collection_name=KNOWLEDGE_VECTOR_COLLECTION)


def ensure_embedding_config_available() -> None:
    """
    Raise when the embedding API key is not resolved.

    Raises:
        RuntimeError: If embeddings cannot be called.
    """
    embedding_config: dict[str, Any] = dict(load_config().get("embedding_model") or {})
    api_key: str = resolve_secret(str(embedding_config.get("api_key") or "$OPENROUTER_API_KEY"))
    if api_key.startswith("$"):
        raise RuntimeError("embedding model API key unresolved")
    get_embedding("knowledge vector readiness")


def knowledge_doc_id(scope: str, kind: str, record_id: int) -> str:
    """Return a stable vector document ID."""
    return f"{scope}:knowledge:{kind}:{record_id}"


def entity_vector_text(entity_row: dict[str, Any]) -> str:
    """Build vector text for one entity row."""
    assertion_text: str = " ".join(
        " ".join(
            (
                str(assertion.get("entity_class") or ""),
                str(assertion.get("description") or ""),
                str(assertion.get("source_path") or ""),
            ),
        )
        for assertion in entity_row.get("type_assertions", [])
        if isinstance(assertion, dict)
    )
    return " ".join(
        str(value or "")
        for value in (
            "knowledge entity",
            entity_row.get("entity_class"),
            entity_row.get("canonical_name"),
            entity_row.get("description"),
            assertion_text,
            entity_row.get("source_title"),
            entity_row.get("source_path"),
        )
    )


def relation_vector_text(relation_row: dict[str, Any]) -> str:
    """Build vector text for one relation row."""
    return " ".join(
        str(value or "")
        for value in (
            "knowledge relation",
            relation_row.get("subject_class"),
            relation_row.get("subject_name"),
            relation_row.get("predicate"),
            relation_row.get("object_class"),
            relation_row.get("object_name"),
            relation_row.get("source_path"),
        )
    )


def entity_vector_metadata(scope: str, entity_row: dict[str, Any]) -> dict[str, Any]:
    """Build Chroma metadata for one entity row."""
    return {
        "knowledge_scope": scope,
        "knowledge_kind": "entity",
        "record_id": int(entity_row["id"]),
    }


def relation_vector_metadata(scope: str, relation_row: dict[str, Any]) -> dict[str, Any]:
    """Build Chroma metadata for one relation row."""
    return {
        "knowledge_scope": scope,
        "knowledge_kind": "relation",
        "record_id": int(relation_row["id"]),
    }
