# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""SQLite-backed workspace log store."""

from __future__ import annotations

# Standard Libraries Imports
import datetime
import sqlite3
import time
from pathlib import Path

# Application Modules Imports
from brain.application.logs.entry_formatting import normalize_log_time
from brain.application.logs.index_renderer import render_logs_index
from brain.application.logs.parsing import parse_log_timestamp
from brain.application.logs.records import LogEntryRecord


LOGS_DB_NAME = "brain_logs.db"
"""Workspace-local SQLite database filename for structured logs."""


class ClosingLogsConnection(sqlite3.Connection):
    """SQLite connection that closes itself after context-manager use."""

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        """Commit or roll back, then close the database handle."""
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False


def get_logs_database_path(workspace_root: Path) -> Path:
    """
    Return the workspace-local logs database path.

    Args:
        workspace_root (Path): Workspace root.

    Returns:
        Path: `$agent/database/brain_logs.db`.
    """
    return workspace_root / "$agent" / "database" / LOGS_DB_NAME


def connect_logs_database(workspace_root: Path) -> sqlite3.Connection:
    """
    Open the logs database and ensure the schema exists.

    Args:
        workspace_root (Path): Workspace root.

    Returns:
        sqlite3.Connection: Open row-factory connection.
    """
    database_path: Path = get_logs_database_path(workspace_root=workspace_root)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, factory=ClosingLogsConnection)
    connection.row_factory = sqlite3.Row
    initialize_logs_schema(connection=connection)
    return connection


def initialize_logs_schema(connection: sqlite3.Connection) -> None:
    """
    Ensure logs database tables exist.

    Args:
        connection (sqlite3.Connection): Open database connection.
    """
    # Migrate backlog_tasks to include TODO status in constraint if needed
    cursor = connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='backlog_tasks'")
    row = cursor.fetchone()
    if row and "CHECK(status IN ('WORKING', 'DONE'))" in str(row[0]):
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("ALTER TABLE backlog_tasks RENAME TO backlog_tasks_old")
        connection.execute("""
            CREATE TABLE backlog_tasks (
                task_id TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL CHECK(priority IN ('HIGH', 'MEDIUM', 'LOW')),
                status TEXT NOT NULL CHECK(status IN ('TODO', 'WORKING', 'DONE')),
                completed_at TEXT NOT NULL DEFAULT '',
                legacy_source TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL DEFAULT 0
            )
        """)
        connection.execute("""
            INSERT INTO backlog_tasks(task_id, domain, title, description, priority, status, completed_at, legacy_source, created_at, updated_at)
            SELECT task_id, domain, title, description, priority, status, completed_at, legacy_source, created_at, updated_at FROM backlog_tasks_old
        """)
        connection.execute("DROP TABLE backlog_tasks_old")
        connection.commit()

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS log_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            date_text TEXT NOT NULL,
            time_text TEXT NOT NULL DEFAULT '',
            timestamp_sort TEXT NOT NULL DEFAULT '',
            domain TEXT NOT NULL,
            title TEXT NOT NULL,
            change_type TEXT NOT NULL,
            why TEXT NOT NULL,
            description TEXT NOT NULL,
            impact TEXT NOT NULL,
            source_path TEXT NOT NULL DEFAULT '',
            source_mtime REAL NOT NULL DEFAULT 0,
            source_size INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL DEFAULT 0,
            updated_at REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS log_index_latest (
            domain TEXT PRIMARY KEY,
            entry_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            date_text TEXT NOT NULL,
            time_text TEXT NOT NULL DEFAULT '',
            timestamp_sort TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            change_type TEXT NOT NULL,
            updated_at REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(entry_id) REFERENCES log_entries(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_log_entries_date_time
            ON log_entries(date_text, time_text, id);
        CREATE INDEX IF NOT EXISTS idx_log_entries_timestamp
            ON log_entries(timestamp);
        CREATE INDEX IF NOT EXISTS idx_log_entries_sort_id
            ON log_entries(timestamp_sort, id);
        CREATE INDEX IF NOT EXISTS idx_log_entries_domain_sort
            ON log_entries(domain, timestamp_sort);
        CREATE INDEX IF NOT EXISTS idx_log_entries_domain_date_sort
            ON log_entries(domain, date_text, timestamp_sort);
        CREATE INDEX IF NOT EXISTS idx_log_entries_date_domain_sort
            ON log_entries(date_text, domain, timestamp_sort);
        CREATE INDEX IF NOT EXISTS idx_log_entries_source_path
            ON log_entries(source_path);
        CREATE INDEX IF NOT EXISTS idx_log_entries_source_fingerprint
            ON log_entries(source_path, source_mtime, source_size);
        CREATE INDEX IF NOT EXISTS idx_log_index_latest_sort
            ON log_index_latest(timestamp_sort, domain);

        CREATE TABLE IF NOT EXISTS backlog_tasks (
            task_id TEXT PRIMARY KEY,
            domain TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            priority TEXT NOT NULL CHECK(priority IN ('HIGH', 'MEDIUM', 'LOW')),
            status TEXT NOT NULL CHECK(status IN ('TODO', 'WORKING', 'DONE')),
            completed_at TEXT NOT NULL DEFAULT '',
            legacy_source TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL DEFAULT 0,
            updated_at REAL NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_backlog_tasks_domain
            ON backlog_tasks(domain, task_id);
        CREATE INDEX IF NOT EXISTS idx_backlog_tasks_status
            ON backlog_tasks(status, updated_at);
        """,
    )
    connection.commit()


def insert_log_entry(workspace_root: Path, entry: LogEntryRecord) -> int:
    """
    Insert one structured log entry and refresh its domain index.

    Args:
        workspace_root (Path): Workspace root.
        entry (LogEntryRecord): Entry to insert.

    Returns:
        int: Inserted row identifier.
    """
    with connect_logs_database(workspace_root=workspace_root) as connection:
        entry_id: int = insert_log_entry_connection(connection=connection, entry=entry)
        refresh_log_index_connection(connection=connection)
        connection.commit()
    return entry_id


def replace_source_entries(workspace_root: Path, source_path: str, entries: list[LogEntryRecord]) -> None:
    """
    Replace all entries imported from one stable source path.

    Args:
        workspace_root (Path): Workspace root.
        source_path (str): Stable source path.
        entries (list[LogEntryRecord]): Parsed entries for that source.
    """
    with connect_logs_database(workspace_root=workspace_root) as connection:
        connection.execute(
            """
            DELETE FROM log_entries
            WHERE source_path = ?
                AND (source_mtime != 0 OR source_size != 0)
            """,
            (source_path,),
        )
        for entry in entries:
            insert_log_entry_connection(connection=connection, entry=entry)
        refresh_log_index_connection(connection=connection)
        connection.commit()


def update_log_entry_by_timestamp(workspace_root: Path, timestamp: str, replacement: LogEntryRecord) -> int | None:
    """
    Update the first entry matching a timestamp.

    Args:
        workspace_root (Path): Workspace root.
        timestamp (str): Existing entry timestamp.
        replacement (LogEntryRecord): Replacement values.

    Returns:
        int | None: Updated row id when found.
    """
    with connect_logs_database(workspace_root=workspace_root) as connection:
        row = connection.execute(
            """
            SELECT id, source_path, source_mtime, source_size
            FROM log_entries
            WHERE timestamp = ?
            ORDER BY id
            LIMIT 1
            """,
            (timestamp,),
        ).fetchone()
        if row is None:
            return None
        stored_replacement = LogEntryRecord(
            timestamp=replacement.timestamp,
            domain=replacement.domain,
            title=replacement.title,
            change_type=replacement.change_type,
            why=replacement.why,
            description=replacement.description,
            impact=replacement.impact,
            source_path=str(row["source_path"] or replacement.source_path),
            source_mtime=float(row["source_mtime"] or replacement.source_mtime),
            source_size=int(row["source_size"] or replacement.source_size),
        )
        date_text, time_text, timestamp_sort = timestamp_parts(timestamp=stored_replacement.timestamp)
        connection.execute(
            """
            UPDATE log_entries
            SET timestamp = ?,
                date_text = ?,
                time_text = ?,
                timestamp_sort = ?,
                domain = ?,
                title = ?,
                change_type = ?,
                why = ?,
                description = ?,
                impact = ?,
                source_path = ?,
                source_mtime = ?,
                source_size = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                stored_replacement.timestamp,
                date_text,
                time_text,
                timestamp_sort,
                stored_replacement.domain,
                stored_replacement.title,
                stored_replacement.change_type,
                stored_replacement.why,
                stored_replacement.description,
                stored_replacement.impact,
                stored_replacement.source_path,
                stored_replacement.source_mtime,
                stored_replacement.source_size,
                time.time(),
                int(row["id"]),
            ),
        )
        refresh_log_index_connection(connection=connection)
        connection.commit()
        return int(row["id"])


def get_log_entry_by_timestamp(workspace_root: Path, timestamp: str) -> LogEntryRecord | None:
    """
    Return the first entry matching a canonical timestamp.

    Args:
        workspace_root (Path): Workspace root.
        timestamp (str): Canonical log timestamp.

    Returns:
        LogEntryRecord | None: Matching entry when present.
    """
    with connect_logs_database(workspace_root=workspace_root) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM log_entries
            WHERE timestamp = ?
            ORDER BY id
            LIMIT 1
            """,
            (timestamp,),
        ).fetchone()
    if row is None:
        return None
    return row_to_log_entry(row=row)


def list_log_entries(
    workspace_root: Path,
    date_text: str | None = None,
    time_text: str | None = None,
    domain: str | None = None,
    from_sort: str | None = None,
    to_sort: str | None = None,
    newest_first: bool = False,
) -> list[LogEntryRecord]:
    """
    List structured log entries from the database.

    Args:
        workspace_root (Path): Workspace root.
        date_text (str | None): Optional DD-MM-YYYY date filter.
        time_text (str | None): Optional HH:MM time filter.
        domain (str | None): Optional domain prefix filter.
        from_sort (str | None): Optional inclusive sortable lower bound.
        to_sort (str | None): Optional inclusive sortable upper bound.
        newest_first (bool): Sort descending when true.

    Returns:
        list[LogEntryRecord]: Matching entries.
    """
    clauses: list[str] = []
    values: list[str] = []
    if date_text:
        clauses.append("date_text = ?")
        values.append(date_text)
    if time_text:
        clauses.append("time_text = ?")
        values.append(time_text)
    if domain:
        clauses.append("(domain = ? OR domain LIKE ?)")
        values.extend([domain, f"{domain}.%"])
    if from_sort:
        clauses.append("timestamp_sort >= ?")
        values.append(from_sort)
    if to_sort:
        clauses.append("timestamp_sort <= ?")
        values.append(to_sort)
    where_sql: str = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order_sql: str = "DESC" if newest_first else "ASC"
    with connect_logs_database(workspace_root=workspace_root) as connection:
        rows = connection.execute(
            f"""
            SELECT *
            FROM log_entries
            {where_sql}
            ORDER BY timestamp_sort {order_sql}, id {order_sql}
            """,
            tuple(values),
        ).fetchall()
    return [row_to_log_entry(row=row) for row in rows]


def log_database_summary(workspace_root: Path) -> tuple[int, int, int]:
    """
    Return counts for the DB-backed log store.

    Args:
        workspace_root (Path): Workspace root.

    Returns:
        tuple[int, int, int]: Entry count, distinct domain count, latest-index row count.
    """
    with connect_logs_database(workspace_root=workspace_root) as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS entry_count,
                COUNT(DISTINCT domain) AS domain_count
            FROM log_entries
            """,
        ).fetchone()
        latest_row = connection.execute("SELECT COUNT(*) AS latest_count FROM log_index_latest").fetchone()
    return int(row["entry_count"]), int(row["domain_count"]), int(latest_row["latest_count"])


def list_log_domains(workspace_root: Path) -> list[str]:
    """Return all distinct normalized log domains from persistent storage."""
    with connect_logs_database(workspace_root=workspace_root) as connection:
        rows = connection.execute(
            "SELECT DISTINCT domain FROM log_entries WHERE domain <> '' ORDER BY domain",
        ).fetchall()
    return [str(row["domain"]) for row in rows]


def rendered_logs_index(workspace_root: Path, domain_filter: str | None = None) -> str:
    """
    Render the DB-backed latest domain index as Markdown.

    Args:
        workspace_root (Path): Workspace root.
        domain_filter (str | None): Optional domain filter.

    Returns:
        str: Human-readable log index Markdown.
    """
    latest_entries: dict[str, tuple[datetime.datetime, str, str, str, str]] = {}
    query = """
        SELECT
            log_index_latest.domain,
            log_index_latest.timestamp,
            log_index_latest.timestamp_sort,
            log_index_latest.change_type,
            log_index_latest.title,
            log_entries.source_path
        FROM log_index_latest
        JOIN log_entries ON log_entries.id = log_index_latest.entry_id
    """
    params = []
    if domain_filter:
        query += " WHERE log_index_latest.domain = ? OR log_index_latest.domain LIKE ?"
        params.extend([domain_filter, f"{domain_filter}.%"])
    query += " ORDER BY log_index_latest.domain"

    with connect_logs_database(workspace_root=workspace_root) as connection:
        rows = connection.execute(query, tuple(params)).fetchall()
    for row in rows:
        parsed_dt: datetime.datetime = parse_log_timestamp(str(row["timestamp"]))
        source_path: str = str(row["source_path"] or source_path_from_date(str(row["timestamp"])[:10]))
        rel_path: str = source_path.replace("$agent/logs/", "", 1)
        latest_entries[str(row["domain"])] = (
            parsed_dt,
            str(row["timestamp"]),
            rel_path,
            str(row["change_type"] or ""),
            str(row["title"] or ""),
        )
    return render_logs_index(latest_entries=latest_entries)


def refresh_log_index(workspace_root: Path) -> None:
    """
    Rebuild the DB-backed latest-domain index.

    Args:
        workspace_root (Path): Workspace root.
    """
    with connect_logs_database(workspace_root=workspace_root) as connection:
        refresh_log_index_connection(connection=connection)
        connection.commit()


def insert_log_entry_connection(connection: sqlite3.Connection, entry: LogEntryRecord) -> int:
    """Insert one log entry using an existing transaction."""
    date_text, time_text, timestamp_sort = timestamp_parts(timestamp=entry.timestamp)
    now_timestamp: float = time.time()
    cursor = connection.execute(
        """
        INSERT INTO log_entries(
            timestamp,
            date_text,
            time_text,
            timestamp_sort,
            domain,
            title,
            change_type,
            why,
            description,
            impact,
            source_path,
            source_mtime,
            source_size,
            created_at,
            updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry.timestamp,
            date_text,
            time_text,
            timestamp_sort,
            entry.domain,
            entry.title,
            entry.change_type,
            entry.why,
            entry.description,
            entry.impact,
            entry.source_path or source_path_from_date(date_text=date_text),
            float(entry.source_mtime),
            int(entry.source_size),
            now_timestamp,
            now_timestamp,
        ),
    )
    return int(cursor.lastrowid)


def refresh_log_index_connection(connection: sqlite3.Connection) -> None:
    """Rebuild the latest-domain projection in an existing transaction."""
    connection.execute("DELETE FROM log_index_latest")
    rows = connection.execute(
        """
        SELECT log_entries.*
        FROM log_entries
        JOIN (
            SELECT domain, MAX(timestamp_sort || printf('%012d', id)) AS sort_key
            FROM log_entries
            GROUP BY domain
        ) latest
            ON latest.domain = log_entries.domain
            AND latest.sort_key = log_entries.timestamp_sort || printf('%012d', log_entries.id)
        """
    ).fetchall()
    now_timestamp: float = time.time()
    for row in rows:
        connection.execute(
            """
            INSERT INTO log_index_latest(
                domain,
                entry_id,
                timestamp,
                date_text,
                time_text,
                timestamp_sort,
                title,
                change_type,
                updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(row["domain"]),
                int(row["id"]),
                str(row["timestamp"]),
                str(row["date_text"]),
                str(row["time_text"]),
                str(row["timestamp_sort"]),
                str(row["title"]),
                str(row["change_type"]),
                now_timestamp,
            ),
        )


def timestamp_parts(timestamp: str) -> tuple[str, str, str]:
    """
    Return date, time, and sortable timestamp strings.

    Args:
        timestamp (str): Canonical log timestamp.

    Returns:
        tuple[str, str, str]: Date text, HH:MM time text, ISO-like sort key.
    """
    date_text: str = timestamp.split(" ")[0]
    parsed_dt: datetime.datetime = parse_log_timestamp(timestamp)
    if parsed_dt == datetime.datetime.min:
        return date_text, "", date_text
    time_text: str = normalize_log_time(parsed_dt.strftime("%H:%M"))
    return date_text, time_text, parsed_dt.strftime("%Y-%m-%d %H:%M:%S")


def source_path_from_date(date_text: str) -> str:
    """
    Return the virtual stable log source path for a date.

    Args:
        date_text (str): DD-MM-YYYY date text.

    Returns:
        str: Stable `$agent/logs/...` source path.
    """
    try:
        parsed_date = datetime.datetime.strptime(date_text, "%d-%m-%Y")
    except ValueError:
        return f"$agent/logs/{date_text}.log.md"
    return f"$agent/logs/{parsed_date.strftime('%Y-%m')}/{date_text}.log.md"


def row_to_log_entry(row: sqlite3.Row) -> LogEntryRecord:
    """Convert one SQLite row into a log entry record."""
    return LogEntryRecord(
        timestamp=str(row["timestamp"]),
        domain=str(row["domain"]),
        title=str(row["title"]),
        change_type=str(row["change_type"]),
        why=str(row["why"]),
        description=str(row["description"]),
        impact=str(row["impact"]),
        source_path=str(row["source_path"] or ""),
        source_mtime=float(row["source_mtime"] or 0.0),
        source_size=int(row["source_size"] or 0),
    )
