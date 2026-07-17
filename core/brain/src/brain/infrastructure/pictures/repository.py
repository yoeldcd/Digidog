"""SQLite repository for image metadata and descriptions."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from brain.infrastructure.pictures.models import PictureRecord
from brain.infrastructure.runtime.paths import get_picture_database_path


class PictureRepository:
    """Persist and query canonical picture records."""

    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = (database_path or get_picture_database_path()).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS pictures (
                    id TEXT PRIMARY KEY,
                    relative_path TEXT NOT NULL UNIQUE,
                    domain TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    width INTEGER NOT NULL DEFAULT 0,
                    height INTEGER NOT NULL DEFAULT 0,
                    description TEXT NOT NULL DEFAULT '',
                    description_source TEXT NOT NULL DEFAULT '',
                    described_at TEXT NOT NULL DEFAULT '',
                    vector_fingerprint TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pictures_domain ON pictures(domain, filename);
                CREATE INDEX IF NOT EXISTS idx_pictures_hash ON pictures(content_hash, active);
                CREATE INDEX IF NOT EXISTS idx_pictures_active ON pictures(active, relative_path);
                """,
            )
            columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(pictures)").fetchall()}
            if "vector_fingerprint" not in columns:
                connection.execute("ALTER TABLE pictures ADD COLUMN vector_fingerprint TEXT NOT NULL DEFAULT ''")

    def list(self, domain: str = "", active_only: bool = True) -> list[PictureRecord]:
        """List pictures, optionally scoped to one domain subtree."""
        clauses: list[str] = []
        values: list[object] = []
        if active_only:
            clauses.append("active = 1")
        if domain:
            clauses.append("(domain = ? OR domain LIKE ?)")
            values.extend([domain, f"{domain}.%"])
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                f"SELECT * FROM pictures{where} ORDER BY domain, filename, relative_path",
                values,
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def get(self, picture_id: str = "", relative_path: str = "") -> PictureRecord | None:
        """Return one picture by id or normalized relative path."""
        if not picture_id and not relative_path:
            return None
        column, value = ("id", picture_id) if picture_id else ("relative_path", relative_path)
        with closing(self._connect()) as connection, connection:
            row = connection.execute(f"SELECT * FROM pictures WHERE {column} = ?", (value,)).fetchone()
        return self._from_row(row) if row is not None else None

    def search(self, query: str, domain: str = "", limit: int = 20) -> list[PictureRecord]:
        """Search canonical filenames, domains, paths, and descriptions."""
        terms = [term for term in query.casefold().split() if term]
        clauses = ["active = 1"]
        values: list[object] = []
        if terms:
            term_clauses: list[str] = []
            for term in terms:
                term_clauses.append(
                    "(LOWER(filename) LIKE ? OR LOWER(relative_path) LIKE ? OR LOWER(domain) LIKE ? OR LOWER(description) LIKE ?)"
                )
                pattern = f"%{term}%"
                values.extend([pattern, pattern, pattern, pattern])
            clauses.append(f"({' OR '.join(term_clauses)})")
        if domain:
            clauses.append("(domain = ? OR domain LIKE ?)")
            values.extend([domain, f"{domain}.%"])
        bounded_limit = max(1, min(int(limit), 500))
        values.append(500)
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                f"SELECT * FROM pictures WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC, relative_path LIMIT ?",
                values,
            ).fetchall()
        records = [self._from_row(row) for row in rows]
        return sorted(
            records,
            key=lambda record: (
                -sum(term in " ".join((record.filename, record.relative_path, record.domain, record.description)).casefold() for term in terms),
                record.relative_path,
            ),
        )[:bounded_limit]

    def find_active_by_hash(self, content_hash: str, excluded_paths: set[str]) -> PictureRecord | None:
        """Find a prior active record with matching bytes outside current scan paths."""
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                "SELECT * FROM pictures WHERE content_hash = ? AND active = 1 ORDER BY updated_at",
                (content_hash,),
            ).fetchall()
        candidates = [self._from_row(row) for row in rows if str(row["relative_path"]) not in excluded_paths]
        return candidates[0] if len(candidates) == 1 else None

    def upsert(self, record: PictureRecord) -> None:
        """Insert or update one canonical picture without discarding its description."""
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO pictures (
                    id, relative_path, domain, filename, extension, mime_type,
                    size_bytes, mtime_ns, content_hash, width, height,
                    description, description_source, described_at, vector_fingerprint, active,
                    created_at, updated_at
                ) VALUES (
                    :id, :relative_path, :domain, :filename, :extension, :mime_type,
                    :size_bytes, :mtime_ns, :content_hash, :width, :height,
                    :description, :description_source, :described_at, :vector_fingerprint, :active,
                    :created_at, :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    relative_path = excluded.relative_path,
                    domain = excluded.domain,
                    filename = excluded.filename,
                    extension = excluded.extension,
                    mime_type = excluded.mime_type,
                    size_bytes = excluded.size_bytes,
                    mtime_ns = excluded.mtime_ns,
                    content_hash = excluded.content_hash,
                    width = excluded.width,
                    height = excluded.height,
                    description = excluded.description,
                    description_source = excluded.description_source,
                    described_at = excluded.described_at,
                    vector_fingerprint = excluded.vector_fingerprint,
                    active = excluded.active,
                    updated_at = excluded.updated_at
                """,
                record.as_mapping(),
            )

    def update_description(self, picture_id: str, description: str, source: str, described_at: str) -> PictureRecord:
        """Replace the description metadata for one registered picture."""
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE pictures
                SET description = ?, description_source = ?, described_at = ?, vector_fingerprint = '', updated_at = ?
                WHERE id = ? AND active = 1
                """,
                (description, source, described_at, described_at, picture_id),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Unknown active picture `{picture_id}`.")
        record = self.get(picture_id=picture_id)
        if record is None:
            raise ValueError(f"Unknown picture `{picture_id}`.")
        return record

    def mark_vector_indexed(self, picture_id: str, fingerprint: str) -> None:
        """Persist the canonical search-text fingerprint after vector indexing."""
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE pictures SET vector_fingerprint = ? WHERE id = ?",
                (fingerprint, picture_id),
            )

    def deactivate_missing(self, active_paths: set[str], updated_at: str) -> list[str]:
        """Mark records absent from the current filesystem scan as inactive."""
        with closing(self._connect()) as connection, connection:
            rows = connection.execute("SELECT id, relative_path FROM pictures WHERE active = 1").fetchall()
            missing_ids = [str(row["id"]) for row in rows if str(row["relative_path"]) not in active_paths]
            if missing_ids:
                connection.executemany(
                    "UPDATE pictures SET active = 0, updated_at = ? WHERE id = ?",
                    [(updated_at, picture_id) for picture_id in missing_ids],
                )
        return missing_ids

    @staticmethod
    def _from_row(row: sqlite3.Row) -> PictureRecord:
        """Hydrate one DTO from SQLite."""
        return PictureRecord(
            id=str(row["id"]), relative_path=str(row["relative_path"]), domain=str(row["domain"]),
            filename=str(row["filename"]), extension=str(row["extension"]), mime_type=str(row["mime_type"]),
            size_bytes=int(row["size_bytes"]), mtime_ns=int(row["mtime_ns"]), content_hash=str(row["content_hash"]),
            width=int(row["width"]), height=int(row["height"]), description=str(row["description"]),
            description_source=str(row["description_source"]), described_at=str(row["described_at"]),
            vector_fingerprint=str(row["vector_fingerprint"]),
            active=bool(row["active"]), created_at=str(row["created_at"]), updated_at=str(row["updated_at"]),
        )
