# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Knowledge graph backend adapter for global query orchestration."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.application.knowledge.runtime.scopes import iter_knowledge_roots
from brain.application.knowledge.querying.query import query_knowledge
from brain.application.knowledge.vector_sync import search_knowledge_vectors
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.application.knowledge.sources.freshness import check_source_updates
from brain.application.querying.dtos import GlobalQueryResultDTO, QueryContentDTO, QueryEntityDTO, QueryRelationDTO
from brain.application.querying.knowledge_mapping import wrap_knowledge_result, source_ref_from_knowledge_data
from brain.application.querying.text_mapping import compact_excerpt
from brain.application.sources.registry_service import ensure_brain_source_indexes


def query_knowledge_backend(text: str, limit: int, knowledge_scope: str) -> list[GlobalQueryResultDTO]:
    """
    Search the SQLite knowledge graph backend.

    Args:
        text (str): Query text.
        limit (int): Maximum knowledge graph matches.
        knowledge_scope (str): Knowledge DB selector.

    Returns:
        list[GlobalQueryResultDTO]: Normalized knowledge results.
    """
    results: list[GlobalQueryResultDTO] = []
    for scope_name, knowledge_root in iter_knowledge_roots(scope=knowledge_scope):
        try:
            repository = KnowledgeRepository(knowledge_root=knowledge_root, scope=scope_name)
            update_check: dict[str, Any] = check_source_updates(
                repository=repository,
                source_scope=scope_name,
            )
            if int(update_check.get("changed") or 0) or int(update_check.get("deleted") or 0):
                results.append(
                    GlobalQueryResultDTO(
                        source="knowledge",
                        mechanism="graph",
                        kind="warning",
                        rank=998.0,
                        title=f"Knowledge graph has source updates pending ({scope_name})",
                        content=QueryContentDTO(
                            title=f"Knowledge graph has source updates pending ({scope_name})",
                            excerpt=(
                                f"{update_check.get('changed', 0)} changed and "
                                f"{update_check.get('deleted', 0)} deleted sources need a dream pass."
                            ),
                        ),
                        warning=(
                            f"{update_check.get('changed', 0)} changed and "
                            f"{update_check.get('deleted', 0)} deleted sources need a dream pass."
                        ),
                        data={"knowledge_scope": scope_name, "source_updates": update_check},
                    ),
                )
            knowledge_matches: list[dict[str, Any]] = query_knowledge(
                repository=repository,
                text=text,
                limit=limit,
                hybrid=False,
            )
        except Exception as exc:
            results.append(
                GlobalQueryResultDTO(
                    source="knowledge",
                    mechanism="graph",
                    kind="warning",
                    rank=999.0,
                    title=f"Knowledge graph unavailable ({scope_name})",
                    warning=str(exc),
                    data={"knowledge_scope": scope_name},
                ),
            )
            continue
        results.extend(
            wrap_knowledge_result(result=result, knowledge_scope=scope_name, query_text=text)
            for result in knowledge_matches
        )
    return results


def run_source_index_fast_pass() -> list[GlobalQueryResultDTO]:
    """
    Refresh lightweight source indexes before querying knowledge backends.

    Returns:
        list[GlobalQueryResultDTO]: Warning results when index refresh fails.
    """
    try:
        ensure_brain_source_indexes()
    except Exception as exc:
        return [
            GlobalQueryResultDTO(
                source="query",
                mechanism="source-index",
                kind="warning",
                rank=999.0,
                title="Source index fast-pass failed",
                content=QueryContentDTO(title="Source index fast-pass failed", excerpt=str(exc)),
                warning=str(exc),
            ),
        ]
    return []


def query_knowledge_vector_backend(text: str, limit: int, knowledge_scope: str) -> list[GlobalQueryResultDTO]:
    """
    Search knowledge graph vectors across selected graph scopes.

    Args:
        text (str): Query text.
        limit (int): Maximum vector matches.
        knowledge_scope (str): Knowledge DB selector.

    Returns:
        list[GlobalQueryResultDTO]: Normalized knowledge vector results.
    """
    results: list[GlobalQueryResultDTO] = []
    for scope_name, knowledge_root in iter_knowledge_roots(scope=knowledge_scope):
        try:
            repository = KnowledgeRepository(knowledge_root=knowledge_root, scope=scope_name)
            vector_matches: list[dict[str, Any]] = search_knowledge_vectors(
                repository=repository,
                text=text,
                limit=limit,
            )
        except Exception as exc:
            results.append(
                GlobalQueryResultDTO(
                    source="knowledge",
                    mechanism="vector",
                    kind="warning",
                    rank=999.0,
                    title=f"Knowledge vectorstore unavailable ({scope_name})",
                    content=QueryContentDTO(
                        title=f"Knowledge vectorstore unavailable ({scope_name})",
                        excerpt=str(exc),
                    ),
                    warning=str(exc),
                    data={"knowledge_scope": scope_name},
                ),
            )
            continue
        results.extend(
            wrap_knowledge_vector_result(match=match, knowledge_scope=scope_name)
            for match in vector_matches
        )
    return results


def wrap_knowledge_vector_result(match: dict[str, Any], knowledge_scope: str) -> GlobalQueryResultDTO:
    """
    Convert one knowledge vector match into a global query result.

    Args:
        match (dict[str, Any]): Vectorstore match.
        knowledge_scope (str): Knowledge scope.

    Returns:
        GlobalQueryResultDTO: Normalized result.
    """
    metadata: dict[str, Any] = dict(match.get("metadata") or {})
    kind: str = str(metadata.get("knowledge_kind") or "knowledge")
    text: str = str(match.get("text") or "")
    title: str = knowledge_vector_title(metadata=metadata, kind=kind)
    data: dict[str, Any] = dict(metadata)
    data.update(
        {
            "source_path": metadata.get("source_path", ""),
            "source_type": metadata.get("source_type", ""),
            "source_title": metadata.get("source_title", ""),
            "knowledge_scope": knowledge_scope,
        },
    )
    return GlobalQueryResultDTO(
        source="knowledge",
        mechanism="vector",
        kind=f"{kind}_vector",
        rank=1.0 - float(match.get("similarity", 0.0)),
        title=title,
        text=text,
        data=data,
        content=QueryContentDTO(
            title=title,
            excerpt=compact_excerpt(text=text, limit=900),
            body=text,
        ),
        source_ref=source_ref_from_knowledge_data(data=data, scope=knowledge_scope),
        entities=knowledge_vector_entities(metadata=metadata, kind=kind),
        relations=knowledge_vector_relations(metadata=metadata, kind=kind),
    )


def knowledge_vector_title(metadata: dict[str, Any], kind: str) -> str:
    """Return the display title for a knowledge vector match."""
    if kind == "relation":
        return " - ".join(
            value
            for value in (
                str(metadata.get("subject_name") or ""),
                str(metadata.get("predicate") or ""),
                str(metadata.get("object_name") or ""),
            )
            if value
        )
    return str(metadata.get("entity_name") or "")


def knowledge_vector_entities(metadata: dict[str, Any], kind: str) -> list[QueryEntityDTO]:
    """Return entities attached to one knowledge vector match."""
    if kind == "relation":
        return [
            QueryEntityDTO(
                id=optional_int(metadata.get("subject_id")),
                entity_class=str(metadata.get("subject_class") or ""),
                name=str(metadata.get("subject_name") or ""),
            ),
            QueryEntityDTO(
                id=optional_int(metadata.get("object_id")),
                entity_class=str(metadata.get("object_class") or ""),
                name=str(metadata.get("object_name") or ""),
            ),
        ]
    return [
        QueryEntityDTO(
            id=optional_int(metadata.get("entity_id")),
            entity_class=str(metadata.get("entity_class") or ""),
            name=str(metadata.get("entity_name") or ""),
            description=str(metadata.get("entity_description") or ""),
        ),
    ]


def knowledge_vector_relations(metadata: dict[str, Any], kind: str) -> list[QueryRelationDTO]:
    """Return relations attached to one knowledge vector match."""
    if kind != "relation":
        return []
    entities: list[QueryEntityDTO] = knowledge_vector_entities(metadata=metadata, kind=kind)
    return [
        QueryRelationDTO(
            id=optional_int(metadata.get("relation_id")),
            predicate=str(metadata.get("predicate") or ""),
            subject=entities[0],
            object=entities[1],
            source_path=str(metadata.get("source_path") or ""),
        ),
    ]


def optional_int(value: Any) -> int | None:
    """Convert optional vector metadata values into integers."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


_query_knowledge_backend = query_knowledge_backend
_query_knowledge_vector_backend = query_knowledge_vector_backend
_run_source_index_fast_pass = run_source_index_fast_pass
