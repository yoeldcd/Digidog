# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Global query orchestration across memory and knowledge stores."""

from __future__ import annotations

# Standard Libraries Imports
from datetime import datetime
from typing import Any

# Application Modules Imports
from brain.application.knowledge.runtime.scopes import normalize_knowledge_scope
from brain.application.querying.context import build_query_context
from brain.application.querying.dtos import GlobalQueryResultDTO, QueryContentDTO, QueryDeepResponseDTO, QuerySubqueryDTO
from brain.application.querying.entity_selection import select_deep_entities
from brain.application.querying.backends.knowledge import (
    query_knowledge_backend,
    query_knowledge_vector_backend,
    run_source_index_fast_pass,
)
from brain.application.querying.backends.memory import query_memory_backend, query_memory_text_backend
from brain.application.querying.backends.messages import query_messages_backend, query_messages_vector_backend
from brain.application.querying.backends.pictures import query_pictures_backend, query_pictures_vector_backend
from brain.application.querying.planning import plan_deep_subqueries
from brain.application.querying.ranking import (
    deduplicate_query_results,
    has_selected_backend,
    query_result_key,
    score_deep_results,
    sort_query_results,
    unique_strings,
    warning_texts,
)
from brain.application.querying.selectors import MAX_DEEP_EVIDENCE_RESULTS, QUERY_MECHANISM_VALUES, QUERY_SOURCE_VALUES
from brain.application.querying.synthesis import synthesize_deep_answer


def query_global(
    text: str,
    domain: str = "all",
    limit: int = 5,
    scope: str = "all",
    source: str | None = None,
    mechanism: str = "all",
    knowledge_scope: str = "all",
    refresh_sources: bool = True,
) -> list[GlobalQueryResultDTO]:
    """
    Search all selected brain knowledge backends through one service.

    Args:
        text (str): User query text.
        domain (str): Optional memory domain filter. Defaults to `all`.
        limit (int): Maximum matches per selected backend.
        scope (str): Backward-compatible source scope: `all`, `memory`, or `knowledge`.
        source (str | None): Preferred source selector. Overrides `scope` when provided.
        mechanism (str): Search mechanism: `all`, `graph`, `vector`, or `text`.
        knowledge_scope (str): Knowledge DB selector: `all`, `global`, or `local`.
        refresh_sources (bool): Whether to run the lightweight source-index fast pass.

    Returns:
        list[GlobalQueryResultDTO]: Normalized results and non-blocking warnings.

    Raises:
        ValueError: If `scope` or `mechanism` is not supported.
    """
    selected_source: str = source if source is not None else scope
    normalized_scope: str = selected_source.casefold().strip()
    normalized_mechanism: str = mechanism.casefold().strip()
    if normalized_scope not in QUERY_SOURCE_VALUES:
        raise ValueError(
            f"Unsupported query source `{selected_source}`. Use one of: all, memory, knowledge, messages, pictures."
        )
    if normalized_mechanism not in QUERY_MECHANISM_VALUES:
        raise ValueError(f"Unsupported query mechanism `{mechanism}`. Use one of: all, graph, vector, text.")
    normalized_knowledge_scope: str = normalize_knowledge_scope(scope=knowledge_scope, allow_all=True)

    bounded_limit: int = max(1, limit)
    results: list[GlobalQueryResultDTO] = []
    if refresh_sources and normalized_scope in ("all", "knowledge"):
        results.extend(run_source_index_fast_pass())

    if normalized_scope in ("all", "knowledge") and normalized_mechanism in ("all", "graph"):
        results.extend(
            query_knowledge_backend(
                text=text,
                limit=bounded_limit,
                knowledge_scope=normalized_knowledge_scope,
            ),
        )

    if normalized_scope in ("all", "knowledge") and normalized_mechanism in ("all", "vector"):
        results.extend(
            query_knowledge_vector_backend(
                text=text,
                limit=bounded_limit,
                knowledge_scope=normalized_knowledge_scope,
            ),
        )

    if normalized_scope in ("all", "memory") and normalized_mechanism in ("all", "vector"):
        results.extend(query_memory_backend(text=text, domain=domain, limit=bounded_limit))

    if normalized_scope in ("all", "memory") and normalized_mechanism in ("all", "text"):
        results.extend(query_memory_text_backend(text=text, domain=domain, limit=bounded_limit))
    if normalized_scope in ("all", "messages") and normalized_mechanism in ("all", "vector"):
        results.extend(query_messages_vector_backend(text=text, limit=bounded_limit))
    if normalized_scope in ("all", "messages") and normalized_mechanism in ("all", "text"):
        results.extend(query_messages_backend(text=text, limit=bounded_limit))
    if normalized_scope in ("all", "pictures") and normalized_mechanism in ("all", "text"):
        results.extend(query_pictures_backend(text=text, domain=domain, limit=bounded_limit))
    if normalized_scope in ("all", "pictures") and normalized_mechanism in ("all", "vector"):
        results.extend(query_pictures_vector_backend(text=text, limit=bounded_limit))

    if not results and not has_selected_backend(
        source=normalized_scope,
        mechanism=normalized_mechanism,
    ):
        return [
            GlobalQueryResultDTO(
                source="query",
                mechanism=normalized_mechanism,
                kind="warning",
                rank=999.0,
                title="No compatible backend selected",
                content=QueryContentDTO(
                    title="No compatible backend selected",
                    excerpt="The selected source and mechanism combination has no query backend.",
                ),
                warning="The selected source and mechanism combination has no query backend.",
            ),
        ]

    return sort_query_results(results=results)


def query_deep(
    text: str,
    domain: str = "all",
    limit: int = 5,
    scope: str = "all",
    source: str | None = None,
    mechanism: str = "all",
    knowledge_scope: str = "all",
    as_of: datetime | None = None,
) -> QueryDeepResponseDTO:
    """
    Segment a query, retrieve supporting matches, and synthesize a contextual answer.

    The LLM selector and synthesizer run only when configured; deterministic fallbacks are always available.

    Args:
        text (str): User query text.
        domain (str): Optional memory domain filter.
        limit (int): Maximum matches per selected backend and subquery.
        scope (str): Backward-compatible source scope.
        source (str | None): Preferred source selector. Overrides `scope` when provided.
        mechanism (str): Search mechanism selector.
        knowledge_scope (str): Knowledge DB selector.
        as_of (datetime | None): Optional deterministic clock value.

    Returns:
        QueryDeepResponseDTO: Contextual answer plus subqueries and evidence.
    """
    bounded_limit: int = max(1, limit)
    context = build_query_context(text=text, as_of=as_of)
    planned_subqueries: list[QuerySubqueryDTO] = plan_deep_subqueries(text=text, context=context, as_of=as_of)
    subqueries: list[QuerySubqueryDTO] = []
    deep_results: list[GlobalQueryResultDTO] = []
    deep_keys: set[tuple[Any, ...]] = set()
    warnings: list[str] = []

    for index, planned_subquery in enumerate(planned_subqueries, 1):
        raw_results: list[GlobalQueryResultDTO] = query_global(
            text=planned_subquery.text,
            domain=domain,
            limit=bounded_limit,
            scope=scope,
            source=source,
            mechanism=mechanism,
            knowledge_scope=knowledge_scope,
            refresh_sources=index == 1,
        )
        warnings.extend(warning_texts(results=raw_results))
        subquery_results: list[GlobalQueryResultDTO] = deduplicate_query_results(
            results=raw_results,
            include_warnings=False,
        )[:bounded_limit]
        subqueries.append(
            planned_subquery.model_copy(update={"index": index, "results": subquery_results}),
        )
        for result in subquery_results:
            result_key: tuple[Any, ...] = query_result_key(result=result)
            if result_key in deep_keys:
                continue
            deep_keys.add(result_key)
            deep_results.append(result)
            if len(deep_results) >= MAX_DEEP_EVIDENCE_RESULTS:
                break
        if len(deep_results) >= MAX_DEEP_EVIDENCE_RESULTS:
            break

    selected_entities, selector_warnings = select_deep_entities(context=context, results=deep_results)
    warnings.extend(selector_warnings)
    deep_results = score_deep_results(
        results=deep_results,
        context=context,
        selected_entities=selected_entities,
    )[:MAX_DEEP_EVIDENCE_RESULTS]
    answer, synthesis_warnings = synthesize_deep_answer(
        query_text=text,
        context=context,
        subqueries=subqueries,
        selected_entities=selected_entities,
        results=deep_results,
    )
    warnings.extend(synthesis_warnings)
    return QueryDeepResponseDTO(
        query=text,
        answer=answer,
        context=context,
        subqueries=subqueries,
        selected_entities=selected_entities,
        results=deep_results,
        warnings=unique_strings(values=warnings),
    )
