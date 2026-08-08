# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Workspace message-history backend for global text query."""

from __future__ import annotations

from brain.application.querying.dtos import GlobalQueryResultDTO, QueryContentDTO, QuerySourceRefDTO
from brain.infrastructure.messages.repository import MessageRepository
from brain.infrastructure.runtime.paths import get_workspace_root
from brain.infrastructure.vectorstores.messages import search_message_vectors


from brain.application.querying.language import extract_query_keywords


def query_messages_backend(text: str, limit: int | None) -> list[GlobalQueryResultDTO]:
    """Search persisted avatar messages in the active local consumer with broad keyword fallback.

    Args:
        text (str): Text query applied to persisted messages. Falls back to extracted keywords when exact match is empty.
        limit (int): Maximum number of results.

    Returns:
        list[GlobalQueryResultDTO]: Ranked text-backed message results.
    """
    repository = MessageRepository(consumer_path=get_workspace_root(), require_registered=False)
    records = repository.list_messages(query=text, limit=limit)
    if not records:
        keywords = extract_query_keywords(query=text, min_length=3)
        if keywords:
            seen_ids: set[str] = set()
            records = []
            for keyword in keywords:
                keyword_records = repository.list_messages(query=keyword, limit=limit)
                for record in keyword_records:
                    if record.id not in seen_ids:
                        seen_ids.add(record.id)
                        records.append(record)
                        if limit is not None and len(records) >= limit:
                            break
                if limit is not None and len(records) >= limit:
                    break
    results: list[GlobalQueryResultDTO] = []
    for rank, record in enumerate(records, 1):
        title: str = record.source_command or f"Avatar message at {record.created_at}"
        results.append(
            GlobalQueryResultDTO(
                source="messages",
                mechanism="text",
                kind="message",
                rank=float(rank),
                title=title,
                text=record.text,
                data=record.as_mapping(),
                content=QueryContentDTO(
                    title=title,
                    excerpt=record.text[:600],
                    body=record.text,
                    location=record.created_at,
                ),
                source_ref=QuerySourceRefDTO(
                    scope="local",
                    source_type="messages",
                    domain="messages",
                    read_command=f"list-messages --query {text!r} --json",
                    path=f"$agent/database/messages.db#message:{record.id}",
                    title=title,
                    structure=["messages", record.date if hasattr(record, "date") else record.created_at[:10]],
                ),
            ),
        )
    return results


def query_messages_vector_backend(text: str, limit: int | None) -> list[GlobalQueryResultDTO]:
    """Search message embeddings and hydrate every result from SQLite.

    Args:
        text (str): Semantic search query.
        limit (int): Maximum number of results.

    Returns:
        list[GlobalQueryResultDTO]: Hydrated vector results or an availability warning.
    """
    workspace_root = get_workspace_root()
    try:
        matches = search_message_vectors(consumer_path=workspace_root, text=text, limit=limit)
    except Exception as exc:
        return [
            GlobalQueryResultDTO(
                source="messages",
                mechanism="vector",
                kind="warning",
                rank=999.0,
                title="Message vectorstore unavailable",
                content=QueryContentDTO(title="Message vectorstore unavailable", excerpt=str(exc)),
                warning=str(exc),
            ),
        ]
    results: list[GlobalQueryResultDTO] = []
    for match in matches:
        record = match["record"]
        title: str = record.source_command or f"Avatar message at {record.created_at}"
        results.append(
            GlobalQueryResultDTO(
                source="messages",
                mechanism="vector",
                kind="message",
                rank=1.0 - float(match.get("similarity", 0.0)),
                title=title,
                text=record.text,
                data=record.as_mapping(),
                content=QueryContentDTO(
                    title=title,
                    excerpt=record.text[:600],
                    body=record.text,
                    location=record.created_at,
                ),
                source_ref=QuerySourceRefDTO(
                    scope="local",
                    source_type="messages",
                    domain="messages",
                    read_command=f"list-messages --query {text!r} --json",
                    path=f"$agent/database/messages.db#message:{record.id}",
                    title=title,
                    structure=["messages", record.created_at[:10]],
                ),
            ),
        )
    return results
