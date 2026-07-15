"""KnowledgeDeltaRepositoryMixin for the SQLite knowledge repository."""

from __future__ import annotations

# Standard Libraries Imports
import json
import time
from typing import Any


class KnowledgeDeltaRepositoryMixin:
    def record_pending_delta(self, source_id: int, payload: dict[str, Any], validation: dict[str, Any]) -> int:
        """
        Store a proposed delta and validation report.

        Args:
            source_id (int): Source identifier.
            payload (dict[str, Any]): Delta JSON payload.
            validation (dict[str, Any]): Validation JSON payload.

        Returns:
            int: Pending delta identifier.
        """
        with self.session() as connection:
            cursor = connection.execute(
                """
                INSERT INTO pending_deltas(source_id, payload_json, validation_json, status, created_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (source_id, json.dumps(payload), json.dumps(validation), "pending", time.time()),
            )
            connection.commit()
        return int(cursor.lastrowid)

    def list_pending_deltas(
        self,
        limit: int = 10,
        status: str = "pending",
    ) -> list[dict[str, Any]]:
        """
        Return pending delta review rows.

        Args:
            limit (int): Maximum rows to return.
            status (str): Delta status filter or `all`.

        Returns:
            list[dict[str, Any]]: Pending delta rows with parsed JSON payloads.
        """
        bounded_limit: int = max(1, limit)
        status_filter: str = status.casefold().strip()
        query_text: str = """
            SELECT
                pending_deltas.*,
                sources.path AS source_path,
                sources.source_type AS source_type,
                sources.title AS source_title
            FROM pending_deltas
            JOIN sources ON sources.id = pending_deltas.source_id
        """
        params: list[Any] = []
        if status_filter != "all":
            query_text += " WHERE pending_deltas.status = ?"
            params.append(status_filter)
        query_text += " ORDER BY pending_deltas.id DESC LIMIT ?"
        params.append(bounded_limit)

        with self.session() as connection:
            rows = connection.execute(query_text, tuple(params)).fetchall()
        return [
            self._pending_delta_row_to_payload(row=dict(row))
            for row in rows
        ]

    def get_pending_delta(self, delta_id: int) -> dict[str, Any] | None:
        """
        Return one pending delta review row.

        Args:
            delta_id (int): Pending delta identifier.

        Returns:
            dict[str, Any] | None: Parsed delta payload when found.
        """
        with self.session() as connection:
            row = connection.execute(
                """
                SELECT
                    pending_deltas.*,
                    sources.path AS source_path,
                    sources.source_type AS source_type,
                    sources.title AS source_title
                FROM pending_deltas
                JOIN sources ON sources.id = pending_deltas.source_id
                WHERE pending_deltas.id = ?
                """,
                (delta_id,),
            ).fetchone()
        return self._pending_delta_row_to_payload(row=dict(row)) if row else None

    def update_pending_delta_status(self, delta_id: int, status: str) -> None:
        """
        Update the review status for one pending delta.

        Args:
            delta_id (int): Pending delta identifier.
            status (str): New lifecycle status.
        """
        normalized_status: str = status.casefold().strip()
        with self.session() as connection:
            connection.execute(
                "UPDATE pending_deltas SET status = ? WHERE id = ?",
                (normalized_status, delta_id),
            )
            connection.commit()

    def update_pending_delta_validation(self, delta_id: int, validation: dict[str, Any]) -> None:
        """
        Cache the latest validation report for one pending delta.

        Args:
            delta_id (int): Pending delta identifier.
            validation (dict[str, Any]): Current deterministic validation payload.
        """
        with self.session() as connection:
            connection.execute(
                "UPDATE pending_deltas SET validation_json = ? WHERE id = ?",
                (json.dumps(validation), delta_id),
            )
            connection.commit()

    def delete_pending_deltas(self, delta_ids: list[int]) -> int:
        """
        Delete pending delta review rows by identifier.

        Args:
            delta_ids (list[int]): Pending delta identifiers to remove.

        Returns:
            int: Number of deleted rows.
        """
        unique_delta_ids: list[int] = sorted({int(delta_id) for delta_id in delta_ids})
        if not unique_delta_ids:
            return 0

        placeholders: str = ", ".join("?" for _ in unique_delta_ids)
        with self.session() as connection:
            cursor = connection.execute(
                f"DELETE FROM pending_deltas WHERE id IN ({placeholders})",
                tuple(unique_delta_ids),
            )
            connection.commit()
        return int(cursor.rowcount)

    def record_applied_delta(self, source_id: int, payload: dict[str, Any]) -> int:
        """
        Store an applied delta audit record.

        Args:
            source_id (int): Source identifier.
            payload (dict[str, Any]): Applied delta JSON payload.

        Returns:
            int: Applied delta identifier.
        """
        with self.session() as connection:
            cursor = connection.execute(
                "INSERT INTO applied_deltas(source_id, payload_json, created_at) VALUES(?, ?, ?)",
                (source_id, json.dumps(payload), time.time()),
            )
            connection.commit()
        return int(cursor.lastrowid)

    def record_dream_run(self, payload: dict[str, Any]) -> int:
        """
        Store a dream consolidation run summary.

        Args:
            payload (dict[str, Any]): Dream run summary payload.

        Returns:
            int: Dream run identifier.
        """
        now_timestamp: float = time.time()
        with self.session() as connection:
            cursor = connection.execute(
                """
                INSERT INTO dream_runs(
                    started_at,
                    finished_at,
                    status,
                    dry_run,
                    sources_seen,
                    deltas_proposed,
                    deltas_applied,
                    errors_json,
                    summary
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("started_at", now_timestamp),
                    payload.get("finished_at", now_timestamp),
                    payload.get("status", "completed"),
                    int(payload.get("dry_run", True)),
                    int(payload.get("sources_seen", 0)),
                    int(payload.get("deltas_proposed", 0)),
                    int(payload.get("deltas_applied", 0)),
                    json.dumps(payload.get("errors", [])),
                    str(payload.get("summary", "")),
                ),
            )
            connection.commit()
        return int(cursor.lastrowid)

    def _pending_delta_row_to_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        """
        Convert one pending delta SQLite row into a review payload.

        Args:
            row (dict[str, Any]): Raw SQLite row.

        Returns:
            dict[str, Any]: Row with parsed payload and validation fields.
        """
        payload: dict[str, Any] = json.loads(str(row.pop("payload_json")))
        validation: dict[str, Any] = json.loads(str(row.pop("validation_json")))
        row["payload"] = payload
        row["validation"] = validation
        return row
