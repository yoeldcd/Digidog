"""Entity selection for deep query synthesis."""

from __future__ import annotations

# Standard Libraries Imports
import json
from typing import Any

# Application Modules Imports
from brain.application.querying.dtos import GlobalQueryResultDTO, QueryContextDTO, QuerySelectedEntityDTO
from brain.application.querying.language import normalize_query_text
from brain.application.querying.llm import request_query_json


def select_deep_entities(
    context: QueryContextDTO,
    results: list[GlobalQueryResultDTO],
    limit: int = 6,
) -> tuple[list[QuerySelectedEntityDTO], list[str]]:
    """
    Select entities relevant to a deep query with LLM auto-fallback.

    Args:
        context (QueryContextDTO): Parsed query context.
        results (list[GlobalQueryResultDTO]): Candidate evidence results.
        limit (int): Maximum selected entities.

    Returns:
        tuple[list[QuerySelectedEntityDTO], list[str]]: Selected entities and warnings.
    """
    deterministic_entities: list[QuerySelectedEntityDTO] = select_entities_deterministically(
        context=context,
        results=results,
        limit=limit,
    )
    candidate_entities: list[QuerySelectedEntityDTO] = collect_candidate_entities(results=results)
    if not candidate_entities:
        return deterministic_entities, []
    try:
        selected_entities = select_entities_with_llm(
            context=context,
            candidates=candidate_entities,
            limit=limit,
        )
        if selected_entities:
            return selected_entities, []
    except Exception as exc:
        return deterministic_entities, [f"LLM entity selector unavailable; deterministic selector used: {exc}"]
    return deterministic_entities, []


def select_entities_deterministically(
    context: QueryContextDTO,
    results: list[GlobalQueryResultDTO],
    limit: int,
) -> list[QuerySelectedEntityDTO]:
    """
    Select entities by keyword overlap and evidence rank.

    Args:
        context (QueryContextDTO): Parsed query context.
        results (list[GlobalQueryResultDTO]): Candidate evidence results.
        limit (int): Maximum selected entities.

    Returns:
        list[QuerySelectedEntityDTO]: Deterministically selected entities.
    """
    scored: dict[tuple[int | None, str], QuerySelectedEntityDTO] = {}
    scores: dict[tuple[int | None, str], float] = {}
    keywords: list[str] = [normalize_query_text(value=keyword) for keyword in context.keywords]
    for result in results:
        for entity in result.entities:
            if not entity.name:
                continue
            key: tuple[int | None, str] = (entity.id, entity.name.casefold())
            entity_blob: str = normalize_query_text(value=f"{entity.name} {entity.entity_class} {entity.description}")
            overlap: int = sum(1 for keyword in keywords if keyword and keyword in entity_blob)
            score: float = overlap + max(0.0, 1.0 - float(result.rank)) + float(entity.confidence or 0.0)
            previous_score: float = scores.get(key, -1.0)
            if score <= previous_score:
                continue
            scores[key] = score
            scored[key] = QuerySelectedEntityDTO(
                id=entity.id,
                name=entity.name,
                entity_class=entity.entity_class,
                confidence=min(1.0, max(0.0, score / 3.0)),
                selector_source="deterministic",
            )
    ordered_keys: list[tuple[int | None, str]] = sorted(scores, key=lambda key: scores[key], reverse=True)
    return [scored[key] for key in ordered_keys[:limit]]


def collect_candidate_entities(results: list[GlobalQueryResultDTO]) -> list[QuerySelectedEntityDTO]:
    """
    Return unique entity candidates from evidence results.

    Args:
        results (list[GlobalQueryResultDTO]): Candidate evidence results.

    Returns:
        list[QuerySelectedEntityDTO]: Candidate entities.
    """
    candidates: list[QuerySelectedEntityDTO] = []
    seen: set[tuple[int | None, str]] = set()
    for result in results:
        for entity in result.entities:
            if not entity.name:
                continue
            key: tuple[int | None, str] = (entity.id, entity.name.casefold())
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                QuerySelectedEntityDTO(
                    id=entity.id,
                    name=entity.name,
                    entity_class=entity.entity_class,
                    confidence=float(entity.confidence or 0.0),
                    selector_source="deterministic",
                ),
            )
    return candidates


def select_entities_with_llm(
    context: QueryContextDTO,
    candidates: list[QuerySelectedEntityDTO],
    limit: int,
) -> list[QuerySelectedEntityDTO]:
    """
    Ask the configured text model to select entity IDs.

    Args:
        context (QueryContextDTO): Parsed query context.
        candidates (list[QuerySelectedEntityDTO]): Candidate entities.
        limit (int): Maximum selected entities.

    Returns:
        list[QuerySelectedEntityDTO]: LLM-selected entities.
    """
    candidate_payloads: list[dict[str, Any]] = [
        {
            "id": candidate.id,
            "name": candidate.name,
            "entity_class": candidate.entity_class,
            "confidence": candidate.confidence,
        }
        for candidate in candidates[:24]
    ]
    payload = request_query_json(
        system_prompt=(
            "Select the most relevant knowledge graph entities for the query. "
            "Return only JSON with an entity_ids array and no prose."
        ),
        user_prompt=json.dumps(
            {
                "query": context.query,
                "keywords": context.keywords,
                "date_constraints": [constraint.model_dump(mode="json") for constraint in context.date_constraints],
                "candidates": candidate_payloads,
                "limit": limit,
            },
            ensure_ascii=False,
        ),
        max_tokens=700,
    )
    selected_ids: list[int] = [
        int(entity_id)
        for entity_id in payload.get("entity_ids", [])
        if str(entity_id).isdigit()
    ]
    selected_by_id: dict[int | None, QuerySelectedEntityDTO] = {
        candidate.id: candidate
        for candidate in candidates
    }
    selected: list[QuerySelectedEntityDTO] = []
    for entity_id in selected_ids:
        candidate = selected_by_id.get(entity_id)
        if candidate is None:
            continue
        selected.append(candidate.model_copy(update={"selector_source": "llm"}))
        if len(selected) >= limit:
            break
    return selected
