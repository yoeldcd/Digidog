"""Filesystem scanners for Brain source registries."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3
from pathlib import Path

# Application Modules Imports
from brain.domain.sources.classification import memory_source_type
from brain.domain.sources.models import DEFAULT_IGNORED_NAMES, SourceRegistryRecordDTO, SourceTypeResolver
from brain.infrastructure.runtime.paths import get_agent_home, get_workspace_root


def scan_memory_source_records(agent_home: Path | None = None) -> list[SourceRegistryRecordDTO]:
    """
    Scan shared memory Markdown sources from the filesystem.

    Args:
        agent_home: Optional agent home override.

    Returns:
        Current memory source records.
    """
    resolved_agent_home: Path = get_agent_home(agent_home=agent_home)
    return scan_tree_source_records(
        root=resolved_agent_home / "memory",
        root_prefix="memory",
        suffixes=(".md",),
        source_type_resolver=memory_source_type,
    )


def scan_log_source_records(workspace_root: Path | None = None) -> list[SourceRegistryRecordDTO]:
    """
    Scan workspace log sources from the filesystem.

    Args:
        workspace_root: Optional workspace root override.

    Returns:
        Current log source records.
    """
    resolved_workspace_root: Path = get_workspace_root(workspace_root=workspace_root)
    database_record = scan_log_database_record(workspace_root=resolved_workspace_root)
    if database_record is not None:
        return [database_record]
    return scan_tree_source_records(
        root=resolved_workspace_root / "$agent" / "logs",
        root_prefix="$agent/logs",
        suffixes=(".log.md",),
        source_type_resolver=lambda _: "workspace_logs",
    )


def scan_log_database_record(workspace_root: Path) -> SourceRegistryRecordDTO | None:
    """
    Return a virtual source record for the DB-backed workspace logs.

    Args:
        workspace_root: Workspace root.

    Returns:
        SourceRegistryRecordDTO | None: Record when the logs DB exists and has entries.
    """
    database_path: Path = workspace_root / "$agent" / "database" / "brain_logs.db"
    if not database_path.exists() or not database_path.is_file():
        return None
    connection = None
    try:
        connection = sqlite3.connect(database_path)
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS entry_count,
                COUNT(DISTINCT domain) AS domain_count
            FROM log_entries
            """,
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        if connection is not None:
            connection.close()
    entry_count = int(row[0] or 0)
    if entry_count <= 0:
        return None
    domain_count = int(row[1] or 0)
    return SourceRegistryRecordDTO(
        path="$agent/database/brain_logs.db",
        mtime=database_path.stat().st_mtime,
        size=_format_size(size_bytes=database_path.stat().st_size),
        lines=str(domain_count),
        entries=entry_count,
        source_type="workspace_logs",
        title="brain_logs",
    )


def scan_tree_source_records(
    root: Path,
    root_prefix: str,
    suffixes: tuple[str, ...],
    source_type_resolver: SourceTypeResolver,
    ignored_names: frozenset[str] = DEFAULT_IGNORED_NAMES,
) -> list[SourceRegistryRecordDTO]:
    """
    Scan a source tree directly from filesystem mtimes.

    Args:
        root: Source directory to scan.
        root_prefix: Stable source path prefix.
        suffixes: File suffixes accepted as source files.
        source_type_resolver: Function that maps paths to source families.
        ignored_names: Names excluded from scanning.

    Returns:
        Current source records.
    """
    if not root.exists():
        return []

    normalized_suffixes: tuple[str, ...] = tuple(suffix.casefold() for suffix in suffixes)
    records: list[SourceRegistryRecordDTO] = []
    for file_path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if not file_path.is_file():
            continue
        if file_path.name in ignored_names or any(part in ignored_names for part in file_path.parts):
            continue
        if not any(file_path.name.casefold().endswith(suffix) for suffix in normalized_suffixes):
            continue
        relative_path: str = file_path.relative_to(root).as_posix()
        source_path: str = f"{root_prefix.rstrip('/')}/{relative_path}".replace("\\", "/")
        size_text, line_text, entry_count = _file_stats(path=file_path)
        records.append(
            SourceRegistryRecordDTO(
                path=source_path,
                mtime=file_path.stat().st_mtime,
                size=size_text,
                lines=line_text,
                entries=entry_count,
                source_type=source_type_resolver(source_path),
                title=file_path.stem,
            ),
        )
    return records


def scan_tree_source_records_incremental(
    root: Path,
    root_prefix: str,
    suffixes: tuple[str, ...],
    source_type_resolver: SourceTypeResolver,
    existing_records: dict[str, SourceRegistryRecordDTO],
    ignored_names: frozenset[str] = DEFAULT_IGNORED_NAMES,
) -> tuple[list[SourceRegistryRecordDTO], bool]:
    """
    Scan a source tree while reusing unchanged registry rows.

    Args:
        root: Source directory to scan.
        root_prefix: Stable source path prefix.
        suffixes: File suffixes accepted as source files.
        source_type_resolver: Function that maps paths to source families.
        existing_records: Active records keyed by stable source path.
        ignored_names: Names excluded from scanning.

    Returns:
        tuple[list[SourceRegistryRecordDTO], bool]: Current records and whether DB refresh is needed.
    """
    if not root.exists():
        return [], bool(existing_records)

    normalized_suffixes: tuple[str, ...] = tuple(suffix.casefold() for suffix in suffixes)
    records: list[SourceRegistryRecordDTO] = []
    active_paths: set[str] = set()
    changed: bool = False
    for file_path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if not file_path.is_file():
            continue
        if file_path.name in ignored_names or any(part in ignored_names for part in file_path.parts):
            continue
        if not any(file_path.name.casefold().endswith(suffix) for suffix in normalized_suffixes):
            continue
        relative_path: str = file_path.relative_to(root).as_posix()
        source_path: str = f"{root_prefix.rstrip('/')}/{relative_path}".replace("\\", "/")
        active_paths.add(source_path)
        file_mtime: float = file_path.stat().st_mtime
        existing_record = existing_records.get(source_path)
        if existing_record is not None and abs(float(existing_record.mtime) - file_mtime) < 0.01:
            records.append(existing_record)
            continue
        changed = True
        records.append(
            scan_source_file_record(
                file_path=file_path,
                root=root,
                root_prefix=root_prefix,
                source_type_resolver=source_type_resolver,
            ),
        )
    if set(existing_records) - active_paths:
        changed = True
    return records, changed


def scan_source_file_record(
    file_path: Path,
    root: Path,
    root_prefix: str,
    source_type_resolver: SourceTypeResolver,
) -> SourceRegistryRecordDTO:
    """
    Build one source registry record from a known source file.

    Args:
        file_path: Source file path.
        root: Source root used to compute stable relative path.
        root_prefix: Stable source path prefix.
        source_type_resolver: Function that maps paths to source families.

    Returns:
        Current source record.
    """
    relative_path: str = file_path.relative_to(root).as_posix()
    source_path: str = f"{root_prefix.rstrip('/')}/{relative_path}".replace("\\", "/")
    size_text, line_text, entry_count = _file_stats(path=file_path)
    return SourceRegistryRecordDTO(
        path=source_path,
        mtime=file_path.stat().st_mtime,
        size=size_text,
        lines=line_text,
        entries=entry_count,
        source_type=source_type_resolver(source_path),
        title=file_path.stem,
    )


def _file_stats(path: Path) -> tuple[str, str, int]:
    """
    Return lightweight source statistics without parsing domain content.

    Args:
        path: Source path.

    Returns:
        Human size, human line count, and heading/list entry count.
    """
    try:
        content: str = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "0KB", "0", 0
    lines: list[str] = content.splitlines()
    entries: int = sum(1 for line in lines if _is_entry_line(line=line))
    size_bytes: int = path.stat().st_size
    return _format_size(size_bytes=size_bytes), _format_line_count(line_count=len(lines)), entries


def _is_entry_line(line: str) -> bool:
    """
    Return whether a line looks like a lightweight source entry.

    Args:
        line: Source line.

    Returns:
        True for markdown headings or keyed list entries.
    """
    stripped_line: str = line.strip()
    if stripped_line.startswith("#"):
        return True
    if not stripped_line.startswith(("-", "*", "+")):
        return False
    marker_text: str = stripped_line[1:].strip()
    return marker_text.startswith("**") and ":" in marker_text


def _format_size(size_bytes: int) -> str:
    """
    Format bytes for source index display.

    Args:
        size_bytes: File size in bytes.

    Returns:
        Compact size label.
    """
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    return f"{size_bytes / 1024:.1f}KB"


def _format_line_count(line_count: int) -> str:
    """
    Format line counts for source index display.

    Args:
        line_count: Number of lines.

    Returns:
        Compact line-count label.
    """
    if line_count >= 1_000_000:
        return f"{line_count / 1_000_000:.1f}M"
    if line_count >= 1_000:
        return f"{line_count / 1_000:.1f}K"
    if line_count >= 100:
        return f"{line_count / 100:.1f}H"
    return str(line_count)
