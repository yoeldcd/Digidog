# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""KnowledgeSourceRepositoryMixin for the SQLite knowledge repository."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3
import time
from typing import Any

# Application Modules Imports
from brain.application.knowledge.models.dtos.sources import EvidenceDTO, SourceDTO
from brain.infrastructure.database.knowledge.utils import hash_text


class KnowledgeSourceRepositoryMixin:
    def upsert_source(self, source_dto: SourceDTO) -> int:
        """
        Insert or update a source record.

        Args:
            source_dto (SourceDTO): Source metadata DTO.

        Returns:
            int: Source database identifier.
        """
        source_values: tuple[Any, ...] = (
            source_dto.source_type,
            source_dto.path,
            source_dto.title,
            int(source_dto.active),
        )
        with self.session() as connection:
            connection.execute(
                """
                INSERT INTO sources(source_type, path, title, active)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    source_type = excluded.source_type,
                    title = excluded.title,
                    active = excluded.active
                """,
                source_values,
            )
            row = connection.execute("SELECT id FROM sources WHERE path = ?", (source_dto.path,)).fetchone()
            connection.commit()
        return int(row["id"])

    def get_source_by_path(self, path: str) -> dict[str, Any] | None:
        """
        Return a source row by path.

        Args:
            path (str): Stable source path.

        Returns:
            dict[str, Any] | None: Source row payload when found.
        """
        with self.session() as connection:
            row = connection.execute("SELECT * FROM sources WHERE path = ?", (path,)).fetchone()
        return dict(row) if row else None

    def add_evidence(self, evidence_dto: EvidenceDTO) -> int:
        """
        Insert or reuse an evidence record.

        Args:
            evidence_dto (EvidenceDTO): Evidence DTO.

        Returns:
            int: Evidence database identifier.
        """
        content_hash: str = evidence_dto.content_hash or hash_text(evidence_dto.quote)
        created_at: float = time.time()
        evidence_values: tuple[Any, ...] = (
            evidence_dto.source_id,
            evidence_dto.quote,
            evidence_dto.location,
            content_hash,
            evidence_dto.confidence,
            created_at,
        )
        with self.session() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO evidence(source_id, quote, location, content_hash, confidence, created_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                evidence_values,
            )
            row = connection.execute(
                "SELECT id FROM evidence WHERE content_hash = ?",
                (content_hash,),
            ).fetchone()
            evidence_id: int = int(row["id"])
            self._refresh_evidence_fts(connection=connection, evidence_id=evidence_id)
            connection.commit()
        return evidence_id

    def _refresh_evidence_fts(self, connection: sqlite3.Connection, evidence_id: int) -> None:
        """
        Refresh one evidence FTS row.

        Args:
            connection (sqlite3.Connection): Open SQLite connection.
            evidence_id (int): Evidence identifier.
        """
        row = connection.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone()
        if row is None:
            return
        connection.execute("DELETE FROM evidence_fts WHERE evidence_id = ?", (evidence_id,))
        connection.execute(
            "INSERT INTO evidence_fts(evidence_id, quote, location) VALUES(?, ?, ?)",
            (evidence_id, row["quote"], row["location"]),
        )
