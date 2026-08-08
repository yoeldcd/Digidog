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
    """Manage source records and source-owned graph assertions."""
    def recompose_source_paths(self, source_paths: list[str]) -> dict[str, int]:
        """Remove assertions owned by sources while retaining generated proposals.

        Args:
            source_paths (list[str]): Stable source paths selected for recomposition.

        Returns:
            dict[str, int]: Counts of removed sources and graph records.
        """
        normalized_paths = sorted({str(path).replace("\\", "/").strip() for path in source_paths if str(path).strip()})
        if not normalized_paths:
            return {"sources": 0, "relations": 0, "assertions": 0, "evidence": 0, "entities": 0}
        placeholders = ", ".join("?" for _path in normalized_paths)
        with self.session() as connection:
            source_rows = connection.execute(
                f"SELECT id FROM sources WHERE replace(path, '\\', '/') IN ({placeholders})",
                tuple(normalized_paths),
            ).fetchall()
            source_ids = [int(row["id"]) for row in source_rows]
            if not source_ids:
                return {"sources": 0, "relations": 0, "assertions": 0, "evidence": 0, "entities": 0}
            id_placeholders = ", ".join("?" for _source_id in source_ids)
            counts = {
                "sources": len(source_ids),
                "relations": _count_rows(connection, "relations", id_placeholders, source_ids),
                "assertions": _count_rows(connection, "entity_type_assertions", id_placeholders, source_ids),
                "evidence": _count_rows(connection, "evidence", id_placeholders, source_ids),
                "entities": 0,
            }
            connection.execute(f"DELETE FROM relations WHERE source_id IN ({id_placeholders})", source_ids)
            connection.execute(f"DELETE FROM evidence WHERE source_id IN ({id_placeholders})", source_ids)
            connection.execute(f"DELETE FROM applied_deltas WHERE source_id IN ({id_placeholders})", source_ids)
            connection.execute(f"DELETE FROM entity_type_assertions WHERE source_id IN ({id_placeholders})", source_ids)
            connection.execute(
                f"""
                UPDATE entities
                SET source_id = (
                    SELECT assertion.source_id
                    FROM entity_type_assertions AS assertion
                    WHERE assertion.entity_id = entities.id AND assertion.source_id IS NOT NULL
                    ORDER BY assertion.confidence DESC, assertion.id ASC
                    LIMIT 1
                )
                WHERE source_id IN ({id_placeholders})
                """,
                source_ids,
            )
            orphan_rows = connection.execute(
                """
                SELECT entity.id
                FROM entities AS entity
                LEFT JOIN entity_type_assertions AS assertion ON assertion.entity_id = entity.id
                LEFT JOIN relations AS subject_relation ON subject_relation.subject_entity_id = entity.id
                LEFT JOIN relations AS object_relation ON object_relation.object_entity_id = entity.id
                WHERE assertion.id IS NULL
                    AND subject_relation.id IS NULL
                    AND object_relation.id IS NULL
                """,
            ).fetchall()
            orphan_ids = [int(row["id"]) for row in orphan_rows]
            counts["entities"] = len(orphan_ids)
            if orphan_ids:
                orphan_placeholders = ", ".join("?" for _entity_id in orphan_ids)
                connection.execute(f"DELETE FROM entity_fts WHERE entity_id IN ({orphan_placeholders})", orphan_ids)
                connection.execute(f"DELETE FROM entities WHERE id IN ({orphan_placeholders})", orphan_ids)
            connection.commit()
        return counts

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


def _count_rows(connection: sqlite3.Connection, table_name: str, placeholders: str, source_ids: list[int]) -> int:
    """Count rows owned by selected source identifiers inside one transaction."""
    row = connection.execute(
        f"SELECT COUNT(*) AS count FROM {table_name} WHERE source_id IN ({placeholders})",
        source_ids,
    ).fetchone()
    return int(row["count"] if row is not None else 0)
