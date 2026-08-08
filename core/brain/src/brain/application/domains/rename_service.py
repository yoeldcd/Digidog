# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Transactional domain-subtree renaming for workspace logs and backlog tasks."""

from __future__ import annotations

# Standard Libraries Imports
import re
import time
from dataclasses import dataclass
from pathlib import Path

# Application Modules Imports
from brain.application.logs.store import connect_logs_database, refresh_log_index_connection


DOMAIN_SEGMENT_PATTERN = re.compile(r"^[a-z0-9_-]+$")


@dataclass(frozen=True, slots=True)
class RenameDomainResult:
    """
    Describe one completed domain mutation.

    Attributes:
        source: Normalized domain path replaced by the operation.
        target: Normalized destination domain path.
        matched: Number of records selected before mutation.
        changed: Number of records updated by SQLite.
        exact: Whether descendants were excluded from the operation.
    """

    source: str
    target: str
    matched: int
    changed: int
    exact: bool


def normalize_domain_path(value: str) -> str:
    """
    Normalize and validate one dot-delimited workspace domain path.

    Args:
        value: Raw domain path supplied by a CLI or API consumer.

    Returns:
        str: Lowercase domain path containing validated non-empty segments.

    Raises:
        ValueError: The path is empty or contains an unsupported segment.
    """
    normalized = ".".join(part.strip().casefold() for part in str(value).split(".") if part.strip())
    if not normalized:
        raise ValueError("Domain must not be empty.")
    if any(DOMAIN_SEGMENT_PATTERN.fullmatch(part) is None for part in normalized.split(".")):
        raise ValueError("Domain segments may contain only letters, numbers, underscores, and hyphens.")
    return normalized


def validate_domain_rename(source: str, target: str) -> tuple[str, str]:
    """
    Return safe source and target paths for one rename operation.

    Args:
        source: Existing domain or subtree root.
        target: Replacement domain or subtree root.

    Returns:
        tuple[str, str]: Normalized source and target paths.

    Raises:
        ValueError: The paths are equal, malformed, or recursively nested.
    """
    normalized_source = normalize_domain_path(value=source)
    normalized_target = normalize_domain_path(value=target)
    if normalized_source == normalized_target:
        raise ValueError("Source and target domains must differ.")
    if normalized_target.startswith(f"{normalized_source}."):
        raise ValueError("A domain cannot be moved inside its own subtree.")
    return normalized_source, normalized_target


def rename_backlog_domain(workspace_root: Path, source: str, target: str, exact: bool = False) -> RenameDomainResult:
    """
    Rename one backlog domain or its complete subtree in a single transaction.

    Args:
        workspace_root: Workspace containing the canonical logs database.
        source: Existing backlog domain path.
        target: Replacement backlog domain path.
        exact: Exclude descendant domains when `True`. Defaults to `False`.

    Returns:
        RenameDomainResult: Normalized paths and affected-record counts.
    """
    normalized_source, normalized_target = validate_domain_rename(source=source, target=target)
    with connect_logs_database(workspace_root=workspace_root) as connection:
        connection.execute("BEGIN IMMEDIATE")
        where_sql, where_values = _domain_where(source=normalized_source, exact=exact)
        matched = int(connection.execute(f"SELECT COUNT(*) FROM backlog_tasks WHERE {where_sql}", where_values).fetchone()[0])
        cursor = connection.execute(
            f"""
            UPDATE backlog_tasks
            SET domain = CASE WHEN lower(domain) = ? THEN ? ELSE ? || substr(domain, length(?) + 1) END,
                updated_at = ?
            WHERE {where_sql}
            """,
            (normalized_source, normalized_target, normalized_target, normalized_source, time.time(), *where_values),
        )
    return RenameDomainResult(normalized_source, normalized_target, matched, cursor.rowcount, exact)


def rename_log_domain(workspace_root: Path, source: str, target: str, exact: bool = False) -> RenameDomainResult:
    """
    Rename one log domain subtree and refresh its SQLite index projection.

    Args:
        workspace_root: Workspace containing the canonical logs database.
        source: Existing log domain path.
        target: Replacement log domain path.
        exact: Exclude descendant domains when `True`. Defaults to `False`.

    Returns:
        RenameDomainResult: Normalized paths and affected-record counts.
    """
    normalized_source, normalized_target = validate_domain_rename(source=source, target=target)
    with connect_logs_database(workspace_root=workspace_root) as connection:
        connection.execute("BEGIN IMMEDIATE")
        where_sql, where_values = _domain_where(source=normalized_source, exact=exact)
        matched = int(connection.execute(f"SELECT COUNT(*) FROM log_entries WHERE {where_sql}", where_values).fetchone()[0])
        cursor = connection.execute(
            f"""
            UPDATE log_entries
            SET domain = CASE WHEN lower(domain) = ? THEN ? ELSE ? || substr(domain, length(?) + 1) END,
                updated_at = ?
            WHERE {where_sql}
            """,
            (normalized_source, normalized_target, normalized_target, normalized_source, time.time(), *where_values),
        )
        refresh_log_index_connection(connection=connection)
    return RenameDomainResult(normalized_source, normalized_target, matched, cursor.rowcount, exact)


def _domain_where(source: str, exact: bool) -> tuple[str, tuple[str, ...]]:
    """
    Return a wildcard-free SQL predicate for an exact domain or subtree.

    Args:
        source: Normalized source domain.
        exact: Whether descendant matching is disabled.

    Returns:
        tuple[str, tuple[str, ...]]: SQL predicate and positional values.
    """
    if exact:
        return "lower(domain) = ?", (source,)
    return "(lower(domain) = ? OR lower(substr(domain, 1, length(?) + 1)) = ? || '.')", (source, source, source)
