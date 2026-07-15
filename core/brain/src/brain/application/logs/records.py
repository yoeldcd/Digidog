"""Structured workspace log entry parsing and rendering."""

from __future__ import annotations

# Standard Libraries Imports
import re
from dataclasses import dataclass

# Application Modules Imports
from brain.application.logs.entry_formatting import build_log_entry_text, normalize_log_type
from brain.application.logs.parsing import to_slug


@dataclass(frozen=True)
class LogEntryRecord:
    """Application record for one structured workspace log entry.

    Attributes:
        timestamp: Canonical entry timestamp.
        domain: Affected changelog domain.
        title: Reader-facing change title.
        change_type: Normalized change type.
        why: Change reason.
        description: Change description.
        impact: Change impact.
        source_path: Stable source path used when imported from Markdown.
        source_mtime: Source modification time used for incremental consumers.
        source_size: Source size in bytes used for diagnostics.
    """

    timestamp: str
    domain: str
    title: str
    change_type: str
    why: str
    description: str
    impact: str
    source_path: str = ""
    source_mtime: float = 0.0
    source_size: int = 0


def parse_log_content(content: str, source_path: str = "", source_mtime: float = 0.0, source_size: int = 0) -> list[LogEntryRecord]:
    """
    Parse canonical Markdown log content into structured records.

    Args:
        content (str): Raw Markdown log file content.
        source_path (str): Stable source path for the parsed file.
        source_mtime (float): Filesystem mtime of the parsed file.
        source_size (int): Filesystem size of the parsed file.

    Returns:
        list[LogEntryRecord]: Parsed entries.
    """
    if "## " not in content:
        return []

    parse_content: str = content if content.startswith("\n") else f"\n{content}"
    _, *entry_parts = parse_content.split("\n## ")
    entries: list[LogEntryRecord] = []
    for part in entry_parts:
        part_clean: str = re.split(r"\n\s*---\s*$", part, flags=re.MULTILINE)[0].strip()
        lines: list[str] = part_clean.splitlines()
        if not lines:
            continue
        timestamp: str = lines[0].strip()
        body_text: str = "\n".join(lines[1:])
        parsed_entry: LogEntryRecord | None = parse_log_entry_body(
            timestamp=timestamp,
            body_text=body_text,
            source_path=source_path,
            source_mtime=source_mtime,
            source_size=source_size,
        )
        if parsed_entry is not None:
            entries.append(parsed_entry)
    return entries


def parse_log_entry_body(
    timestamp: str,
    body_text: str,
    source_path: str = "",
    source_mtime: float = 0.0,
    source_size: int = 0,
) -> LogEntryRecord | None:
    """
    Parse one canonical log entry body.

    Args:
        timestamp (str): Entry timestamp.
        body_text (str): Entry Markdown body without the `##` heading.
        source_path (str): Stable source path for imported entries.
        source_mtime (float): Source mtime.
        source_size (int): Source size in bytes.

    Returns:
        LogEntryRecord | None: Parsed record when the entry is usable.
    """
    if timestamp.startswith("DD-MM-YYYY"):
        return None
    header_match = re.search(r"^### \(([^)]+)\)\s*\[([^\]]+)\]", body_text, re.MULTILINE)
    if header_match is None:
        return None

    domain: str = to_slug(header_match.group(1))
    if domain in ("domain.subdomain", "domain[.subdomain]"):
        return None

    change_type: str = extract_entry_section(
        label_pattern=r"\*\*Type:\*\*\s*\n?(.*?)(?=\s*\*\*Why:\*\*|\s*\*\*Description|\s*\*\*Impact|$)",
        text=body_text,
    )
    if not change_type:
        change_type = "feature"

    return LogEntryRecord(
        timestamp=timestamp,
        domain=domain,
        title=header_match.group(2).strip(),
        change_type=normalize_imported_log_type(change_type=change_type),
        why=extract_entry_section(
            label_pattern=r"\*\*Why:\*\*\s*\n?(.*?)(?=\s*\*\*Description|\s*\*\*Impact|$)",
            text=body_text,
        ),
        description=extract_entry_section(
            label_pattern=description_section_pattern(body_text=body_text),
            text=body_text,
        ),
        impact=extract_entry_section(
            label_pattern=impact_section_pattern(body_text=body_text),
            text=body_text,
        ),
        source_path=source_path,
        source_mtime=source_mtime,
        source_size=source_size,
    )


def render_log_entry(entry: LogEntryRecord) -> str:
    """
    Render one structured log entry as canonical Markdown.

    Args:
        entry (LogEntryRecord): Entry to render.

    Returns:
        str: Canonical Markdown entry.
    """
    return build_log_entry_text(
        timestamp=entry.timestamp,
        log_domain=entry.domain,
        title=entry.title,
        change_type=entry.change_type,
        why=entry.why,
        description=entry.description,
        impact=entry.impact,
    )


def render_log_file(date_text: str, entries: list[LogEntryRecord]) -> str:
    """
    Render one daily Markdown log file from structured entries.

    Args:
        date_text (str): DD-MM-YYYY date label.
        entries (list[LogEntryRecord]): Entries for that date.

    Returns:
        str: Canonical daily log Markdown.
    """
    header_text: str = (
        f"# Log file for date {date_text}\n\n"
        "The entries are ordered in ascending order, from oldest to newest.\n"
    )
    if not entries:
        return f"{header_text}\n"
    entry_blocks: list[str] = [render_log_entry(entry=entry) for entry in entries]
    return f"{header_text}\n---\n\n" + "\n\n---\n\n".join(entry_blocks) + "\n"


def normalize_imported_log_type(change_type: str) -> str:
    """Normalize an imported log type without rejecting historical entries."""
    try:
        return normalize_log_type(change_type=change_type)
    except ValueError:
        normalized = change_type.casefold().strip()
        if normalized in {"doc", "docs"}:
            return "documentation"
        return "feature"


def extract_entry_section(label_pattern: str, text: str) -> str:
    """
    Extract one indented Markdown field section.

    Args:
        label_pattern (str): Regular expression with one capture group.
        text (str): Entry body text.

    Returns:
        str: Normalized section text.
    """
    match = re.search(label_pattern, text, re.DOTALL | re.IGNORECASE)
    if match is None:
        return ""
    lines: list[str] = []
    for line in match.group(1).splitlines():
        lines.append(re.sub(r"^\s{2,4}", "", line))
    return "\n".join(lines).strip()


def description_section_pattern(body_text: str) -> str:
    """
    Return the description regex variant used by an entry.

    Args:
        body_text (str): Entry body text.

    Returns:
        str: Description capture pattern.
    """
    if "**Description**:" in body_text:
        return r"\*\*Description\*\*:\s*\n?(.*?)(?=\s*\*\*Impact|$)"
    return r"\*\*Description\*\*\s*\n?(.*?)(?=\s*\*\*Impact|$)"


def impact_section_pattern(body_text: str) -> str:
    """
    Return the impact regex variant used by an entry.

    Args:
        body_text (str): Entry body text.

    Returns:
        str: Impact capture pattern.
    """
    if "**Impact**:" in body_text:
        return r"\*\*Impact\*\*:\s*\n?(.*?)$"
    return r"\*\*Impact\*\*\s*\n?(.*?)$"
