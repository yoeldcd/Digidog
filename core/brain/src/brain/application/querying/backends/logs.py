"""Workspace log vector and text search backend for global query."""

from __future__ import annotations

from brain.application.profiles.service import (
    render_profile_template_value,
    render_profile_template_variables,
)
from brain.application.querying.dtos import (
    GlobalQueryResultDTO,
    LogSearchDTO,
    QueryContentDTO,
    QuerySourceRefDTO,
)


def query_logs_backend(text: str, limit: int | None) -> list[GlobalQueryResultDTO]:
    """Search indexed workspace logs via vector similarity and direct text matching.

    Args:
        text: Natural-language or keyword search query.
        limit: Maximum number of results.

    Returns:
        Ranked log results as GlobalQueryResultDTO.
    """
    try:
        from brain.infrastructure.vectorstores.manager import VectorStoreManager

        manager = VectorStoreManager()
        try:
            matches = manager.search_logs(query=text, limit=limit)
        finally:
            close_manager = getattr(manager, "close", None)
            if callable(close_manager):
                close_manager()
    except Exception as exc:
        return [
            GlobalQueryResultDTO(
                source="logs",
                mechanism="vector",
                kind="warning",
                rank=999.0,
                title="Log vectorstore unavailable",
                content=QueryContentDTO(
                    title="Log vectorstore unavailable", excerpt=str(exc)
                ),
                warning=str(exc),
            ),
        ]
    results: list[GlobalQueryResultDTO] = []
    for rank, match in enumerate(matches, 1):
        dto = LogSearchDTO(
            id=int(match.get("id") or 0),
            text=str(match.get("text") or ""),
            path=str(match.get("path") or ""),
            domain=str(match.get("domain") or ""),
            title=str(match.get("title") or ""),
            type=str(match.get("type") or ""),
            timestamp=str(match.get("timestamp") or ""),
            read_command=str(match.get("read_command") or ""),
            similarity=float(match.get("similarity") or 0),
            recency_factor=float(match.get("recency_factor") or 0),
            score=float(match.get("score") or 0),
        )
        excerpt = dto.text[:600] if dto.text else ""
        results.append(
            GlobalQueryResultDTO(
                source="logs",
                mechanism="vector",
                kind="log",
                rank=float(rank),
                title=dto.title,
                text=excerpt,
                data=dto.model_dump(mode="json"),
                content=QueryContentDTO(
                    title=dto.title, excerpt=excerpt, body=dto.text
                ),
                source_ref=QuerySourceRefDTO(
                    scope="local",
                    source_type="logs",
                    domain=dto.domain,
                    read_command=dto.read_command,
                    path=dto.path,
                    title=dto.title,
                ),
            )
        )
        results[-1] = _localize_result(results[-1])
    return results


def query_logs_text_backend(text: str, limit: int | None) -> list[GlobalQueryResultDTO]:
    """Search workspace logs via direct SQL text matching on title, description, and impact."""
    try:
        from brain.application.logs.store import connect_logs_database
        from brain.infrastructure.runtime.paths import get_workspace_root

        ws = get_workspace_root()
        with connect_logs_database(workspace_root=ws) as conn:
            words = [w.strip() for w in text.split() if len(w.strip()) >= 3]
            if not words:
                return []
            conditions = " OR ".join(
                ["title LIKE ? OR description LIKE ? OR impact LIKE ? OR why LIKE ?"]
                * len(words)
            )
            params = []
            for w in words:
                params.extend([f"%{w}%"] * 4)
            limit_clause: str = " LIMIT ?" if limit is not None else ""
            query_sql: str = (
                f"SELECT * FROM log_entries WHERE {conditions} "
                f"ORDER BY timestamp_sort DESC{limit_clause}"
            )
            query_params: list[object] = [*params]
            if limit is not None:
                query_params.append(limit)

            rows = conn.execute(query_sql, query_params).fetchall()
    except Exception:
        return []
    results: list[GlobalQueryResultDTO] = []
    for rank, row in enumerate(rows, 1):
        from brain.application.logs.records import LogEntryRecord

        record = LogEntryRecord(
            timestamp=row["timestamp"],
            domain=row["domain"],
            title=row["title"],
            change_type=row["change_type"],
            why=row["why"],
            description=row["description"],
            impact=row["impact"],
            source_path=row["source_path"] or "",
            source_mtime=float(row["source_mtime"] or 0),
            source_size=int(row["source_size"] or 0),
            record_id=int(row["id"]),
        )
        from brain.application.logs.entry_formatting import build_log_entry_text

        body = build_log_entry_text(
            timestamp=record.timestamp,
            log_domain=record.domain,
            title=record.title,
            change_type=record.change_type,
            why=record.why,
            description=record.description,
            impact=record.impact,
        )
        excerpt = body[:600]
        from brain.infrastructure.vectorstores.chunking import (
            normalized_entry_time,
            reader_command_for_entry,
        )

        read_cmd = reader_command_for_entry(
            command_name="read-log",
            date_text=record.timestamp[:10],
            entry_time=normalized_entry_time(record.timestamp),
        )
        dto = LogSearchDTO(
            id=record.record_id,
            text=body,
            path=record.source_path,
            domain=record.domain,
            title=record.title,
            type=record.change_type,
            timestamp=record.timestamp,
            read_command=read_cmd,
        )
        results.append(
            GlobalQueryResultDTO(
                source="logs",
                mechanism="text",
                kind="log",
                rank=float(rank),
                title=dto.title,
                text=excerpt,
                data=dto.model_dump(mode="json"),
                content=QueryContentDTO(title=dto.title, excerpt=excerpt, body=body),
                source_ref=QuerySourceRefDTO(
                    scope="local",
                    source_type="logs",
                    domain=dto.domain,
                    read_command=dto.read_command,
                    path=dto.path,
                    title=dto.title,
                ),
            )
        )
        results[-1] = _localize_result(results[-1])
    return results


def _localize_result(result: GlobalQueryResultDTO) -> GlobalQueryResultDTO:
    """Return a localized public copy without mutating retrieval evidence."""
    content = result.content.model_copy(
        update={
            "title": render_profile_template_variables(result.content.title),
            "excerpt": render_profile_template_variables(result.content.excerpt),
            "body": render_profile_template_variables(result.content.body),
            "location": render_profile_template_variables(result.content.location),
        }
    )
    source_ref = result.source_ref.model_copy(
        update={
            "read_command": render_profile_template_variables(
                result.source_ref.read_command
            ),
            "path": render_profile_template_variables(result.source_ref.path),
            "title": render_profile_template_variables(result.source_ref.title),
        }
    )
    return result.model_copy(
        update={
            "title": render_profile_template_variables(result.title),
            "text": render_profile_template_variables(result.text),
            "warning": render_profile_template_variables(result.warning),
            "data": render_profile_template_value(result.data),
            "content": content,
            "source_ref": source_ref,
        }
    )
