# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Application services owned by the Query Log capability."""

from __future__ import annotations


def resolve_query_log_domain(requested_domain: str | None, available_domains: list[str]) -> str | None:
    """Resolve a requested domain against real domains by hierarchy levels.

    Resolution prefers an exact domain or parent prefix. When absent, leading
    segments are progressively removed (``brain.cli`` -> ``cli``). Finally,
    the remaining path is matched as a complete suffix of an existing domain.
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
