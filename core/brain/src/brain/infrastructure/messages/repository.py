# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""SQLite repository for workspace-local avatar message history."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from brain.infrastructure.messages.models import MessageRecordDTO, MessageWriteDTO
from brain.infrastructure.runtime.paths import get_brain_mirrors_path


MESSAGE_DATABASE_NAME = "messages.db"
MESSAGE_BUSY_TIMEOUT_MS = 5_000
PERSISTED_OPERATION_COMMANDS = frozenset({"add-log", "add-task", "append-log", "complete-work"})


def resolve_registered_consumer_path(consumer_path: str | Path) -> Path:
    """Resolve one consumer only when it is present in the core mirror registry."""
    candidate: Path = Path(consumer_path).expanduser().resolve()
    registry_path: Path = get_brain_mirrors_path()
    try:
        payload: Any = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("The Brain mirror registry is unavailable.") from exc
    registered_paths: set[Path] = {
        Path(str(item.get("path", ""))).expanduser().resolve()
        for item in payload
        if isinstance(item, dict) and str(item.get("path", "")).strip()
    }
    if candidate not in registered_paths:
        raise ValueError(f"Consumer path is not registered as a Brain mirror: {candidate}")
    return candidate


def message_database_path(consumer_path: str | Path, require_registered: bool = True) -> Path:
    """Return the canonical local message database path for one consumer."""
    root: Path = (
        resolve_registered_consumer_path(consumer_path)
        if require_registered
        else Path(consumer_path).expanduser().resolve()
    )
    return root / "$agent" / "database" / MESSAGE_DATABASE_NAME


class MessageRepository:
    """Persist and query immutable avatar messages for one registered consumer."""

    def __init__(self, consumer_path: str | Path, require_registered: bool = True) -> None:
        """Bind the repository without opening a long-lived connection."""
        self.database_path: Path = message_database_path(
            consumer_path=consumer_path,
            require_registered=require_registered,
        )

    def initialize(self) -> Path:
        """Create the database schema and return its path."""
        with closing(self._connect()) as connection:
            connection.commit()
        return self.database_path

    def append(self, message: MessageWriteDTO) -> bool:
        """Insert one idempotent message in a short transaction."""
        normalized: MessageWriteDTO = _normalized_message(message=message)
        content_hash: str = _message_hash(message=normalized)
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO messages(
                    id, created_at, text, emotion, chat_id, language,
                    source_type, source_command, source_phase, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized.id,
                    normalized.created_at,
                    normalized.text,
                    normalized.emotion,
                    normalized.chat_id,
                    normalized.language,
                    normalized.source_type,
                    normalized.source_command,
                    normalized.source_phase,
                    content_hash,
                ),
            )
            connection.commit()
        return cursor.rowcount == 1

    def list_messages(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        chat_id: str = "",
        chat_id_exact: str | None = None,
        emotion: str = "",
        source_command: str = "",
        query: str = "",
        date: str = "",
    ) -> list[MessageRecordDTO]:
        """List newest messages using bounded, parameterized filters."""
        clauses: list[str] = []
        values: list[object] = []
        for column, value in (
            ("chat_id", chat_id),
            ("emotion", emotion),
            ("source_command", source_command),
        ):
            if value.strip():
                clauses.append(f"{column} = ?")
                values.append(value.strip())
        if chat_id_exact is not None:
            clauses.append("chat_id = ?")
            values.append(chat_id_exact.strip())
        if date.strip():
            clauses.append("substr(created_at, 1, 10) = ?")
            values.append(date.strip())
        if query.strip():
            clauses.append("text LIKE ? ESCAPE '\\'")
            values.append(f"%{_escape_like(query.strip())}%")
        where_sql: str = " WHERE " + " AND ".join(clauses) if clauses else ""
        values.extend((max(1, min(500, int(limit))), max(0, int(offset))))
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"""
                SELECT id, created_at, text, emotion, chat_id, language,
                       source_type, source_command, source_phase
                FROM messages{where_sql}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                values,
            ).fetchall()
        return [_record_from_row(row=row) for row in rows]

    def list_session_summaries(self) -> list[dict[str, object]]:
        """Return durable daily session summaries ordered newest first."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT substr(created_at, 1, 10) AS session_date,
                       chat_id,
                       COUNT(*) AS message_count,
                       MIN(created_at) AS started_at,
                       MAX(created_at) AS ended_at
                FROM messages
                GROUP BY session_date, chat_id
                ORDER BY session_date DESC, ended_at DESC
                """
            ).fetchall()
        return [
            {
                "id": f"{row[0]}::{row[1] or 'unassigned'}",
                "date": str(row[0]),
                "chatId": str(row[1]),
                "label": str(row[1]) if str(row[1]) else "Session without chat ID",
                "messageCount": int(row[2]),
                "startedAt": str(row[3]),
                "endedAt": str(row[4]),
            }
            for row in rows
        ]

    def count(self) -> int:
        """Return the number of persisted messages."""
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT COUNT(*) FROM messages").fetchone()
        return int(row[0]) if row else 0

    def get_message(self, message_id: str) -> MessageRecordDTO | None:
        """Return one persisted message by its immutable identifier."""
        normalized_id: str = message_id.strip()
        if not normalized_id:
            return None
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT id, created_at, text, emotion, chat_id, language,
                       source_type, source_command, source_phase
                FROM messages
                WHERE id = ?
                """,
                (normalized_id,),
            ).fetchone()
        return _record_from_row(row=row) if row is not None else None

    def latest_mtime(self) -> float:
        """Return the database mtime used by knowledge freshness checks."""
        candidates: tuple[Path, ...] = (
            self.database_path,
            Path(f"{self.database_path}-wal"),
        )
        mtimes: list[float] = [path.stat().st_mtime for path in candidates if path.is_file()]
        return max(mtimes, default=0.0)

    def export_markdown(self, limit: int = 1_000) -> str:
        """Render recent records as deterministic Markdown for Dream ingestion."""
        records: list[MessageRecordDTO] = self.list_messages(limit=limit)
        lines: list[str] = ["# Avatar Message History", ""]
        for record in reversed(records):
            command_label: str = f" `{record.source_command}:{record.source_phase}`" if record.source_command else ""
            lines.extend(
                (
                    f"## {record.created_at}{command_label}",
                    "",
                    f"- Emotion: `{record.emotion or 'neutral'}`",
                    f"- Chat: `{record.chat_id or 'unassigned'}`",
                    f"- Source: `{record.source_type}`",
                    "",
                    record.text,
                    "",
                ),
            )
        return "\n".join(lines).rstrip() + "\n"

    def _connect(self) -> sqlite3.Connection:
        """Open one configured connection and apply idempotent schema setup."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection: sqlite3.Connection = sqlite3.connect(self.database_path, timeout=5)
        connection.execute(f"PRAGMA busy_timeout={MESSAGE_BUSY_TIMEOUT_MS}")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages(
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                text TEXT NOT NULL CHECK(length(trim(text)) > 0),
                emotion TEXT NOT NULL DEFAULT '',
                chat_id TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL DEFAULT 'es',
                source_type TEXT NOT NULL CHECK(source_type IN ('speak', 'operation')),
                source_command TEXT NOT NULL DEFAULT '',
                source_phase TEXT NOT NULL DEFAULT '',
                content_hash TEXT NOT NULL
            )
            """,
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at DESC)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id, created_at DESC)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_messages_emotion ON messages(emotion, created_at DESC)")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_source_command ON messages(source_command, created_at DESC)",
        )
        return connection


def should_persist_message(source_command: str) -> bool:
    """Return whether an explicit speak or selected operation belongs in history."""
    normalized_command: str = source_command.casefold().strip()
    return not normalized_command or normalized_command in PERSISTED_OPERATION_COMMANDS


def _normalized_message(message: MessageWriteDTO) -> MessageWriteDTO:
    """Normalize bounded message fields before persistence."""
    text: str = message.text.strip()
    if not text:
        raise ValueError("Message text cannot be empty.")
    source_type: str = message.source_type.casefold().strip() or "speak"
    if source_type not in {"speak", "operation"}:
        raise ValueError(f"Unsupported message source type: {source_type}")
    return MessageWriteDTO(
        id=message.id.strip(),
        created_at=message.created_at.strip(),
        text=text,
        emotion=message.emotion.strip(),
        chat_id=message.chat_id.strip(),
        language=message.language.strip() or "es",
        source_type=source_type,
        source_command=message.source_command.casefold().strip(),
        source_phase=message.source_phase.casefold().strip(),
    )


def _message_hash(message: MessageWriteDTO) -> str:
    """Return a stable integrity hash without using it as record identity."""
    value: str = "\x1f".join(
        (
            message.created_at,
            message.text,
            message.emotion,
            message.chat_id,
            message.source_command,
            message.source_phase,
        ),
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _escape_like(value: str) -> str:
    """Escape SQLite LIKE metacharacters for literal substring search."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _record_from_row(row: sqlite3.Row | tuple[object, ...]) -> MessageRecordDTO:
    """Map one repository row to its public DTO."""
    return MessageRecordDTO(
        id=str(row[0]),
        created_at=str(row[1]),
        text=str(row[2]),
        emotion=str(row[3]),
        chat_id=str(row[4]),
        language=str(row[5]),
        source_type=str(row[6]),
        source_command=str(row[7]),
        source_phase=str(row[8]),
    )
