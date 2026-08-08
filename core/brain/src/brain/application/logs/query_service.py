# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Application services owned by the Query Log capability."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from brain.application.logs.records import LogEntryRecord
from brain.application.logs.store import list_log_entries


def resolve_query_log_domain(requested_domain: str | None, available_domains: list[str]) -> str | None:
    """Resolve a requested domain against real domains by hierarchy levels.

    Resolution prefers an exact domain or parent prefix. When absent, leading
    segments are progressively removed (``brain.cli`` -> ``cli``). Finally,
    the remaining path is matched as a complete suffix of an existing domain.

    Args:
        requested_domain (str | None): Domain or partial hierarchy requested by the caller.
        available_domains (list[str]): Canonical domains available in the log store.

    Returns:
        str | None: Resolved owning domain, normalized request, or None when no domain was supplied.
    """
    requested = _normalize_domain(requested_domain)
    if not requested:
        return None
    available = sorted({_normalize_domain(domain) for domain in available_domains if _normalize_domain(domain)})
    for candidate in _level_candidates(requested):
        if _owns_domain(candidate, available):
            return candidate
        suffix_matches = [domain for domain in available if domain == candidate or domain.endswith(f".{candidate}")]
        if suffix_matches:
            return min(suffix_matches, key=lambda domain: (domain.count("."), len(domain), domain))
    return requested


def search_log_text_matches(
    *,
    workspace_root: Path,
    query: str,
    domain_filter: str | None,
    limit: int,
    fallback_reason: str,
) -> list[dict[str, object]]:
    """Search durable logs without requiring an embedding provider.

    Args:
        workspace_root: Workspace containing the canonical logs database.
        query: User-supplied text query.
        domain_filter: Optional resolved domain prefix.
        limit: Maximum number of ranked matches.
        fallback_reason: Non-sensitive reason semantic search was unavailable.

    Returns:
        Vector-compatible result mappings ranked by lexical relevance and time.
    """
    normalized_query = _normalize_search_text(query)
    query_tokens = set(normalized_query.split())
    if not query_tokens:
        return []
    ranked: list[tuple[float, str, LogEntryRecord, str]] = []
    for entry in list_log_entries(
        workspace_root=workspace_root,
        domain=domain_filter,
        newest_first=True,
    ):
        text = _log_search_text(entry)
        normalized_text = _normalize_search_text(text)
        text_tokens = set(normalized_text.split())
        matched_tokens = query_tokens.intersection(text_tokens)
        coverage = len(matched_tokens) / len(query_tokens)
        substring_bonus = 0.3 if normalized_query in normalized_text else 0.0
        similarity = min(1.0, coverage * 0.7 + substring_bonus)
        if similarity <= 0.0:
            continue
        ranked.append((similarity, entry.timestamp, entry, text))
    ranked.sort(key=lambda item: (item[0], item[1], item[2].record_id), reverse=True)
    return [
        {
            "id": f"log.db#{entry.record_id}",
            "text": text,
            "path": entry.source_path or "database/brain_logs.db",
            "domain": entry.domain,
            "title": entry.title,
            "type": entry.change_type,
            "timestamp": entry.timestamp,
            "read_command": _read_log_command(entry.timestamp),
            "similarity": similarity,
            "recency_factor": 1.0,
            "score": similarity,
            "mechanism": "text",
            "fallback_reason": fallback_reason,
        }
        for similarity, _timestamp, entry, text in ranked[: max(0, limit)]
    ]


def _normalize_domain(domain: str | None) -> str:
    """Normalize dot-separated domain notation."""
    return ".".join(part.strip().casefold() for part in str(domain or "").split(".") if part.strip())


def _level_candidates(domain: str) -> list[str]:
    """Return progressively less specific candidates by dropping ancestors."""
    parts = domain.split(".")
    return [".".join(parts[index:]) for index in range(len(parts))]


def _owns_domain(candidate: str, available_domains: list[str]) -> bool:
    """Return whether a candidate is an exact domain or available parent."""
    return any(domain == candidate or domain.startswith(f"{candidate}.") for domain in available_domains)


def _normalize_search_text(value: str) -> str:
    """Return accent-insensitive lowercase tokens for deterministic matching."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(character for character in decomposed if not unicodedata.combining(character))
    return " ".join(re.findall(r"[a-z0-9_]+", plain))


def _log_search_text(entry: LogEntryRecord) -> str:
    """Join searchable fields from one durable log record."""
    values = (entry.domain, entry.title, entry.change_type, entry.why, entry.description, entry.impact)
    return "\n".join(value.strip() for value in values if value.strip())


def _read_log_command(timestamp: str) -> str:
    """Build the canonical precise reader command for one timestamp."""
    date_text = timestamp[:10]
    time_match = re.search(r"\b(\d{1,2}:\d{2})\s*(am|pm)?\b", timestamp[10:], re.IGNORECASE)
    if time_match is None:
        return f"read-log {date_text}"
    suffix = f" {time_match.group(2).lower()}" if time_match.group(2) else ""
    return f"read-log {date_text} --time {time_match.group(1)}{suffix}"
