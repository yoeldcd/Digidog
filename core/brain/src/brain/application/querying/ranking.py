# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Ranking, deduplication, and backend-selection helpers for global query."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.application.querying.dtos import GlobalQueryResultDTO, QueryContextDTO, QueryMatchDTO, QuerySelectedEntityDTO
from brain.application.querying.language import normalize_query_text


def deduplicate_query_results(
    results: list[GlobalQueryResultDTO],
    include_warnings: bool,
) -> list[GlobalQueryResultDTO]:
    """
    Deduplicate normalized query results while preserving backend ranking.

    Args:
        results (list[GlobalQueryResultDTO]): Query results.
        include_warnings (bool): Whether warning rows should be retained.

    Returns:
        list[GlobalQueryResultDTO]: Unique results.
    """
    seen: set[tuple[Any, ...]] = set()
    deduplicated_results: list[GlobalQueryResultDTO] = []
    for result in results:
        if result.kind == "warning" and not include_warnings:
            continue
        result_key: tuple[Any, ...] = query_result_key(result=result)
        if result_key in seen:
            continue
        seen.add(result_key)
        deduplicated_results.append(result)
    return deduplicated_results


def query_result_key(result: GlobalQueryResultDTO) -> tuple[Any, ...]:
    """
    Return a stable identity key for one normalized result.

    Args:
        result (GlobalQueryResultDTO): Query result.

    Returns:
        tuple[Any, ...]: Result identity tuple.
    """
    relation_ids: tuple[int, ...] = tuple(
        relation_id
        for relation_id in (relation.id for relation in result.relations)
        if relation_id is not None
    )
    entity_ids: tuple[int, ...] = tuple(
        entity_id
        for entity_id in (entity.id for entity in result.entities)
        if entity_id is not None
    )
    if relation_ids or entity_ids:
        return (result.source, result.mechanism, result.kind, relation_ids, entity_ids)
    return (
        result.source,
        result.mechanism,
        result.kind,
        result.title.casefold(),
        result.source_ref.path.casefold(),
        result.content.excerpt[:160].casefold(),
        result.warning.casefold(),
    )


def warning_texts(results: list[GlobalQueryResultDTO]) -> list[str]:
    """
    Extract warning texts from query results.

    Args:
        results (list[GlobalQueryResultDTO]): Query results.

    Returns:
        list[str]: Warning texts.
    """
    return [
        result.warning or result.title
        for result in results
        if result.kind == "warning" and (result.warning or result.title)
    ]


def unique_strings(values: list[str]) -> list[str]:
    """
    Return unique non-empty strings in original order.

    Args:
        values (list[str]): Candidate strings.

    Returns:
        list[str]: Unique strings.
    """
    unique_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized_value: str = " ".join(value.split())
        seen_key: str = normalized_value.casefold()
        if not normalized_value or seen_key in seen:
            continue
        seen.add(seen_key)
        unique_values.append(normalized_value)
    return unique_values


def sort_query_results(results: list[GlobalQueryResultDTO]) -> list[GlobalQueryResultDTO]:
    """
    Sort query results while keeping warnings after usable matches.

    Args:
        results (list[GlobalQueryResultDTO]): Unsorted query results.

    Returns:
        list[GlobalQueryResultDTO]: Sorted query results.
    """
    return sorted(
        results,
        key=lambda result: (
            query_result_layer_order(result=result),
            result.source_ref.domain,
            result.rank,
        ),
    )


def score_deep_results(
    results: list[GlobalQueryResultDTO],
    context: QueryContextDTO,
    selected_entities: list[QuerySelectedEntityDTO],
) -> list[GlobalQueryResultDTO]:
    """
    Score and filter deep-query evidence using keywords, dates, and selected entities.

    Args:
        results (list[GlobalQueryResultDTO]): Candidate results.
        context (QueryContextDTO): Parsed query context.
        selected_entities (list[QuerySelectedEntityDTO]): Query-relevant entities.

    Returns:
        list[GlobalQueryResultDTO]: Filtered results with match explanations.
    """
    scored_results: list[GlobalQueryResultDTO] = []
    for result in results:
        if result.kind == "warning":
            scored_results.append(result)
            continue
        match: QueryMatchDTO = match_query_result(
            result=result,
            context=context,
            selected_entities=selected_entities,
        )
        if should_keep_deep_result(match=match, context=context):
            scored_results.append(result.model_copy(update={"match": match}))
    return sorted(
        scored_results,
        key=lambda result: (
            query_result_layer_order(result=result),
            result.match.adjusted_score if result.kind != "warning" else result.rank,
            result.source_ref.domain,
            result.rank,
        ),
    )


def match_query_result(
    result: GlobalQueryResultDTO,
    context: QueryContextDTO,
    selected_entities: list[QuerySelectedEntityDTO],
) -> QueryMatchDTO:
    """
    Explain how one result matches deep-query context.

    Args:
        result (GlobalQueryResultDTO): Candidate result.
        context (QueryContextDTO): Parsed query context.
        selected_entities (list[QuerySelectedEntityDTO]): Query-relevant entities.

    Returns:
        QueryMatchDTO: Match explanation and adjusted score.
    """
    blob: str = result_search_blob(result=result)
    keyword_hits: list[str] = [
        keyword
        for keyword in context.keywords
        if normalize_query_text(value=keyword) in blob
    ]
    keyword_misses: list[str] = [
        keyword
        for keyword in context.keywords
        if keyword not in keyword_hits
    ]
    date_match: str = match_date_constraints(blob=blob, context=context)
    entity_match: bool = any(
        selected_entity.name and normalize_query_text(value=selected_entity.name) in blob
        for selected_entity in selected_entities
    )
    adjusted_score: float = float(result.rank)
    adjusted_score -= 0.12 * len(keyword_hits)
    adjusted_score += 0.18 * len(keyword_misses)
    if context.date_constraints and date_match == "matched":
        adjusted_score -= 0.25
    if context.date_constraints and date_match == "missed":
        adjusted_score += 0.35
    if entity_match:
        adjusted_score -= 0.2
    return QueryMatchDTO(
        keyword_hits=keyword_hits,
        keyword_misses=keyword_misses,
        date_match=date_match,
        entity_match=entity_match,
        explanation=build_match_explanation(
            keyword_hits=keyword_hits,
            keyword_misses=keyword_misses,
            date_match=date_match,
            entity_match=entity_match,
        ),
        adjusted_score=adjusted_score,
    )


def should_keep_deep_result(match: QueryMatchDTO, context: QueryContextDTO) -> bool:
    """
    Return whether a scored result is relevant enough for deep synthesis.

    Args:
        match (QueryMatchDTO): Result match details.
        context (QueryContextDTO): Parsed query context.

    Returns:
        bool: True when the result should be retained.
    """
    if len(context.keywords) < 2:
        return True
    if match.keyword_hits or match.entity_match:
        return True
    return False


def match_date_constraints(blob: str, context: QueryContextDTO) -> str:
    """
    Match normalized date constraints against result text.

    Args:
        blob (str): Normalized result text.
        context (QueryContextDTO): Parsed query context.

    Returns:
        str: none, matched, or missed.
    """
    if not context.date_constraints:
        return "none"
    for constraint in context.date_constraints:
        if any(
            date_text and normalize_query_text(value=date_text) in blob
            for date_text in date_variants(constraint.start)
        ):
            return "matched"
        if constraint.raw and normalize_query_text(value=constraint.raw) in blob:
            return "matched"
        if constraint.label and normalize_query_text(value=constraint.label) in blob:
            return "matched"
    return "missed"


def date_variants(iso_datetime: str) -> list[str]:
    """
    Build common date strings for matching source paths and reader commands.

    Args:
        iso_datetime (str): ISO datetime string.

    Returns:
        list[str]: Date string variants.
    """
    iso_date: str = iso_datetime[:10]
    if len(iso_date) != 10:
        return []
    year, month, day = iso_date.split("-")
    return [
        iso_date,
        f"{day}-{month}-{year}",
        f"{day}/{month}/{year}",
        f"{year}/{month}/{day}",
    ]


def result_search_blob(result: GlobalQueryResultDTO) -> str:
    """
    Build normalized text used by deep ranking.

    Args:
        result (GlobalQueryResultDTO): Query result.

    Returns:
        str: Normalized searchable text.
    """
    values: list[str] = [
        result.title,
        result.text,
        result.content.title,
        result.content.excerpt,
        result.content.body,
        result.content.location,
        result.source_ref.domain,
        result.source_ref.path,
        result.source_ref.title,
        result.source_ref.read_command,
        result.source_ref.source_type,
        " ".join(result.source_ref.structure),
    ]
    for entity in result.entities:
        values.extend([entity.name, entity.entity_class, entity.description])
    for relation in result.relations:
        values.extend(
            [
                relation.predicate,
                relation.subject.name,
                relation.subject.description,
                relation.object.name,
                relation.object.description,
                relation.source_path,
            ],
        )
    return normalize_query_text(value=" ".join(str(value or "") for value in values))


def build_match_explanation(
    keyword_hits: list[str],
    keyword_misses: list[str],
    date_match: str,
    entity_match: bool,
) -> str:
    """
    Build a compact match explanation for terminal and JSON callers.

    Args:
        keyword_hits (list[str]): Keywords found in the result.
        keyword_misses (list[str]): Keywords missing from the result.
        date_match (str): Date match state.
        entity_match (bool): Whether selected entities matched.

    Returns:
        str: Reader-facing match explanation.
    """
    parts: list[str] = []
    if keyword_hits:
        parts.append(f"keywords hit: {', '.join(keyword_hits)}")
    if keyword_misses:
        parts.append(f"keywords missed: {', '.join(keyword_misses)}")
    if date_match != "none":
        parts.append(f"date {date_match}")
    if entity_match:
        parts.append("selected entity matched")
    return "; ".join(parts) or "general relevance"


def query_result_layer_order(result: GlobalQueryResultDTO) -> int:
    """
    Return the display order for evidence layers.

    Args:
        result (GlobalQueryResultDTO): Query result.

    Returns:
        int: Lower values are displayed first.
    """
    if result.source == "memory" and result.mechanism == "text":
        return 0
    if result.kind == "relation":
        return 2
    if result.kind == "warning":
        return 3
    return 1


def has_selected_backend(source: str, mechanism: str) -> bool:
    """
    Return whether a source and mechanism combination maps to any backend.

    Args:
        source (str): Normalized query source.
        mechanism (str): Normalized query mechanism.

    Returns:
        bool: True when at least one backend can run.
    """
    knowledge_selected: bool = source in ("all", "knowledge") and mechanism in ("all", "graph")
    knowledge_vector_selected: bool = source in ("all", "knowledge") and mechanism in ("all", "vector")
    memory_vector_selected: bool = source in ("all", "memory") and mechanism in ("all", "vector")
    memory_text_selected: bool = source in ("all", "memory") and mechanism in ("all", "text")
    message_text_selected: bool = source in ("all", "messages") and mechanism in ("all", "text")
    message_vector_selected: bool = source in ("all", "messages") and mechanism in ("all", "vector")
    picture_text_selected: bool = source in ("all", "pictures") and mechanism in ("all", "text")
    picture_vector_selected: bool = source in ("all", "pictures") and mechanism in ("all", "vector")
    return (
        knowledge_selected
        or knowledge_vector_selected
        or memory_vector_selected
        or memory_text_selected
        or message_text_selected
        or message_vector_selected
        or picture_text_selected
        or picture_vector_selected
    )
