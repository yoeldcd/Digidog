# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Workspace message-history backend for global text query."""

from __future__ import annotations

from brain.application.querying.dtos import GlobalQueryResultDTO, QueryContentDTO, QuerySourceRefDTO
from brain.infrastructure.messages.repository import MessageRepository
from brain.infrastructure.runtime.paths import get_workspace_root
from brain.infrastructure.vectorstores.messages import search_message_vectors


def query_messages_backend(text: str, limit: int) -> list[GlobalQueryResultDTO]:
    """Search persisted avatar words in the active local consumer."""
    repository = MessageRepository(consumer_path=get_workspace_root(), require_registered=False)
    records = repository.list_messages(query=text, limit=limit)
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


def query_messages_vector_backend(text: str, limit: int) -> list[GlobalQueryResultDTO]:
    """Search message embeddings and hydrate every result from SQLite."""
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
