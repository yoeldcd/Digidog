"""Knowledge-graph result mapping into global query DTOs."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.application.querying.dtos import GlobalQueryResultDTO, QueryContentDTO, QueryEntityDTO, QueryRelationDTO, QuerySourceRefDTO
from brain.application.querying.source_refs import source_domain_from_path, source_ref_from_path
from brain.application.querying.text_mapping import compact_excerpt, read_source_excerpt


def wrap_knowledge_result(
    result: dict[str, Any],
    knowledge_scope: str,
    query_text: str,
) -> GlobalQueryResultDTO:
    """
    Convert one knowledge graph match into the global query DTO.

    Args:
        result (dict[str, Any]): Knowledge query result.
        knowledge_scope (str): Scope that produced the result.
        query_text (str): Original query text.

    Returns:
        GlobalQueryResultDTO: Normalized result.
    """
    data: dict[str, Any] = dict(result.get("data", {}))
    data["knowledge_scope"] = knowledge_scope
    kind: str = str(result.get("kind", "knowledge"))
    title: str = knowledge_result_title(kind=kind, data=data)
    source_ref: QuerySourceRefDTO = source_ref_from_knowledge_data(data=data, scope=knowledge_scope)
    entities: list[QueryEntityDTO] = query_entities_from_knowledge_data(kind=kind, data=data)
    relations: list[QueryRelationDTO] = query_relations_from_knowledge_data(data=data)
    content: QueryContentDTO = knowledge_content(
        data=data,
        title=title,
        query_text=query_text,
        source_ref=source_ref,
    )
    return GlobalQueryResultDTO(
        source="knowledge",
        mechanism="graph",
        kind=kind,
        rank=float(result.get("rank", 0.0)),
        title=title,
        text=content.excerpt,
        data=data,
        content=content,
        source_ref=source_ref,
        entities=entities,
        relations=relations,
    )


def source_ref_from_knowledge_data(data: dict[str, Any], scope: str) -> QuerySourceRefDTO:
    """Build a structured source reference from knowledge result data."""
    path: str = str(data.get("source_path") or data.get("path") or "")
    return source_ref_from_path(
        path=path,
        source_type=str(data.get("source_type") or ""),
        title=str(data.get("source_title") or ""),
        scope=scope,
    )


def knowledge_result_title(kind: str, data: dict[str, Any]) -> str:
    """Return the display title for a knowledge result."""
    if kind == "relation":
        subject_name: str = str(data.get("subject_name") or "")
        object_name: str = str(data.get("object_name") or "")
        predicate: str = str(data.get("predicate") or "")
        return f"{subject_name} - {predicate} -> {object_name}".strip(" -")
    source_path: str = str(data.get("source_path") or data.get("path") or "")
    return str(
        data.get("canonical_name")
        or data.get("quote")
        or source_domain_from_path(path=source_path)
        or data.get("id")
        or "",
    )


def knowledge_content(
    data: dict[str, Any],
    title: str,
    query_text: str,
    source_ref: QuerySourceRefDTO,
) -> QueryContentDTO:
    """Build the content block for a knowledge result."""
    direct_text: str = str(
        data.get("content_excerpt")
        or data.get("quote")
        or data.get("description")
        or "",
    ).strip()
    source_excerpt: str = read_source_excerpt(
        source_path=source_ref.path,
        query_text=query_text,
        fallback_terms=[
            title,
            str(data.get("canonical_name") or ""),
            str(data.get("subject_name") or ""),
            str(data.get("object_name") or ""),
            str(data.get("predicate") or ""),
        ],
    )
    excerpt: str = source_excerpt or direct_text
    if direct_text and direct_text not in excerpt:
        excerpt = f"{direct_text}\n\n{excerpt}" if excerpt else direct_text
    return QueryContentDTO(
        title=title,
        excerpt=compact_excerpt(text=excerpt, limit=900),
        body=excerpt,
        location=str(data.get("location") or ""),
    )


def query_entities_from_knowledge_data(kind: str, data: dict[str, Any]) -> list[QueryEntityDTO]:
    """Convert knowledge payload entities into query DTOs."""
    raw_entities: list[dict[str, Any]] = [
        item
        for item in data.get("entities", [])
        if isinstance(item, dict)
    ]
    if not raw_entities and kind == "entity":
        raw_entities = [
            {
                "id": data.get("id"),
                "entity_class": data.get("entity_class", ""),
                "name": data.get("canonical_name", ""),
                "description": data.get("description", ""),
                "confidence": data.get("confidence", 0.0),
                "type_assertions": data.get("type_assertions", []),
            },
        ]
    return [query_entity_from_dict(item) for item in raw_entities]


def query_entity_from_dict(item: dict[str, Any]) -> QueryEntityDTO:
    """Convert a dictionary into a query entity DTO."""
    return QueryEntityDTO(
        id=optional_int(item.get("id")),
        entity_class=str(item.get("entity_class") or item.get("class") or ""),
        name=str(item.get("name") or item.get("canonical_name") or ""),
        description=str(item.get("description") or ""),
        confidence=float(item.get("confidence") or 0.0),
        type_assertions=[
            dict(assertion)
            for assertion in item.get("type_assertions", [])
            if isinstance(assertion, dict)
        ],
    )


def query_relations_from_knowledge_data(data: dict[str, Any]) -> list[QueryRelationDTO]:
    """Convert knowledge payload relations into query DTOs."""
    raw_relations: list[dict[str, Any]] = [
        item
        for item in data.get("relations", [])
        if isinstance(item, dict)
    ]
    return [
        QueryRelationDTO(
            id=optional_int(item.get("id")),
            predicate=str(item.get("predicate") or ""),
            subject=query_entity_from_dict(dict(item.get("subject") or {})),
            object=query_entity_from_dict(dict(item.get("object") or {})),
            confidence=float(item.get("confidence") or 0.0),
            source_path=str(item.get("source_path") or ""),
        )
        for item in raw_relations
    ]


def optional_int(value: Any) -> int | None:
    """Convert optional values into integers when possible."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
