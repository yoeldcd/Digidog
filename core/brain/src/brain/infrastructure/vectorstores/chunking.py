"""Markdown, diary, and log chunking helpers for vector indexing."""

from __future__ import annotations

# Standard Libraries Imports
import re


ENTRY_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
"""Markdown section heading pattern."""

DATED_ENTRY_RE = re.compile(
    r"^(?P<date>\d{2}-\d{2}-\d{4})\s+"
    r"(?P<time>\d{1,2}:\d{2})(?::\d{2})?"
    r"(?:\s*(?P<ampm>[ap]m))?(?:\s+-\s+(?P<title>.+))?$",
    re.IGNORECASE,
)
"""Dated diary/log entry heading pattern."""


def chunk_content(category: str, key: str, content: str) -> list[tuple[str, str, dict]]:
    """Split content into indexable chunks."""
    lines = content.splitlines()
    chunks = []

    has_sections = any(line.startswith("## ") for line in lines)

    from brain.application.memory.paths import resolve_file_path
    try:
        file_path = resolve_file_path(category, key)
        mtime = file_path.stat().st_mtime if file_path.exists() else 0.0
    except Exception:
        mtime = 0.0

    if category == "diary" or category.startswith("diary."):
        return chunk_dated_markdown_entries(
            category=category,
            key=key,
            content=content,
            mtime=mtime,
            path=f"memory/{category.replace('.', '/')}/{key}.md",
            source_kind="diary",
            reader_command="read-diary",
        )

    if not has_sections:
        chunks.append((
            f"{category}.{key}",
            content.strip(),
            {"category": category, "key": key, "title": f"{category}.{key}", "mtime": mtime},
        ))
        return chunks

    current_header = None
    current_lines = []
    slug_counts: dict[str, int] = {}
    base_id = f"{category}.{key}"

    for line in lines:
        if line.startswith("## "):
            if current_header and current_lines:
                text_content = "\n".join(current_lines).strip()
                if text_content:
                    header_slug = markdown_header_slug(header=current_header)
                    chunks.append((
                        unique_chunk_id(base_id=base_id, slug=header_slug, slug_counts=slug_counts),
                        f"{current_header}\n\n{text_content}",
                        {"category": category, "key": key, "title": current_header, "mtime": mtime},
                    ))
            current_header = line.strip()
            current_lines = []
        else:
            if current_header is not None:
                current_lines.append(line)

    if current_header and current_lines:
        text_content = "\n".join(current_lines).strip()
        if text_content:
            header_slug = markdown_header_slug(header=current_header)
            chunks.append((
                unique_chunk_id(base_id=base_id, slug=header_slug, slug_counts=slug_counts),
                f"{current_header}\n\n{text_content}",
                {"category": category, "key": key, "title": current_header, "mtime": mtime},
            ))

    return chunks


def chunk_dated_markdown_entries(
    category: str,
    key: str,
    content: str,
    mtime: float,
    path: str,
    source_kind: str,
    reader_command: str,
) -> list[tuple[str, str, dict]]:
    """Split dated Markdown sources into entry-level vector records."""
    chunks: list[tuple[str, str, dict]] = []
    current_header: str = ""
    current_lines: list[str] = []

    for line in content.splitlines():
        header_match: re.Match[str] | None = ENTRY_HEADING_RE.match(line)
        if header_match is not None:
            append_dated_entry_chunk(
                chunks=chunks,
                category=category,
                key=key,
                header=current_header,
                body_lines=current_lines,
                mtime=mtime,
                path=path,
                source_kind=source_kind,
                reader_command=reader_command,
            )
            current_header = header_match.group(1).strip()
            current_lines = []
            continue
        if current_header:
            current_lines.append(line)

    append_dated_entry_chunk(
        chunks=chunks,
        category=category,
        key=key,
        header=current_header,
        body_lines=current_lines,
        mtime=mtime,
        path=path,
        source_kind=source_kind,
        reader_command=reader_command,
    )
    return chunks


def append_dated_entry_chunk(
    chunks: list[tuple[str, str, dict]],
    category: str,
    key: str,
    header: str,
    body_lines: list[str],
    mtime: float,
    path: str,
    source_kind: str,
    reader_command: str,
) -> None:
    """Append one dated entry vector chunk when it has body text."""
    if not header:
        return
    body_text: str = "\n".join(body_lines).strip()
    if not body_text:
        return
    entry = parse_dated_entry_header(header=header, fallback_date=key)
    entry_slug: str = entry_slug_from_header(header=header)
    read_command: str = reader_command_for_entry(
        command_name=reader_command,
        date_text=entry["date"],
        entry_time=entry["time"],
    )
    chunks.append(
        (
            f"{category}.{key}#{entry_slug}",
            body_text,
            {
                "category": category,
                "key": key,
                "path": path,
                "source_kind": source_kind,
                "title": entry["title"],
                "entry_title": entry["title"],
                "entry_date": entry["date"],
                "entry_time": entry["time"],
                "read_command": read_command,
                "body": body_text,
                "mtime": mtime,
            },
        ),
    )


def parse_dated_entry_header(header: str, fallback_date: str) -> dict[str, str]:
    """Parse a diary or log entry heading into metadata fields."""
    match: re.Match[str] | None = DATED_ENTRY_RE.match(header)
    if match is None:
        return {"date": fallback_date, "time": "", "title": header.strip()}
    entry_time: str = normalize_clock_time(
        time_text=match.group("time"),
        ampm=match.group("ampm") or "",
    )
    return {
        "date": match.group("date"),
        "time": entry_time,
        "title": (match.group("title") or header).strip(),
    }


def normalized_entry_time(header: str) -> str:
    """Return HH:MM from an entry heading."""
    match: re.Match[str] | None = DATED_ENTRY_RE.match(header)
    if match is None:
        return ""
    return normalize_clock_time(time_text=match.group("time"), ampm=match.group("ampm") or "")


def normalize_clock_time(time_text: str, ampm: str = "") -> str:
    """Normalize a clock time to HH:MM."""
    hour_text, minute_text = time_text.split(":", 1)
    hour = int(hour_text)
    minute = int(minute_text[:2])
    normalized_ampm: str = ampm.casefold().strip()
    if normalized_ampm == "pm" and hour < 12:
        hour += 12
    elif normalized_ampm == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def reader_command_for_entry(command_name: str, date_text: str, entry_time: str) -> str:
    """Build a precise CLI reader command."""
    time_text: str = f" --time {entry_time}" if entry_time else ""
    return f"{command_name} -d {date_text}{time_text}"


def entry_slug_from_header(header: str) -> str:
    """Build a stable slug from an entry heading."""
    return re.sub(r"[^a-zA-Z0-9]+", "-", header).strip("-").lower()


def log_entry_body_text(body_text: str) -> str:
    """Return log entry semantic body without the metadata subheading."""
    lines: list[str] = body_text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and lines[0].lstrip().startswith("### "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def markdown_header_slug(header: str) -> str:
    """Build a stable readable slug from a Markdown section header."""
    clean_header = header.strip().lstrip("#").strip().strip(":").casefold()
    slug = re.sub(r"\s+", "-", clean_header)
    slug = re.sub(r"[^a-z0-9_-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-_")
    return slug or "section"


def unique_chunk_id(base_id: str, slug: str, slug_counts: dict[str, int]) -> str:
    """Return a unique chunk ID for repeated section headers inside one file."""
    slug_counts[slug] = slug_counts.get(slug, 0) + 1
    suffix = "" if slug_counts[slug] == 1 else f"-{slug_counts[slug]}"
    return f"{base_id}#{slug}{suffix}"
