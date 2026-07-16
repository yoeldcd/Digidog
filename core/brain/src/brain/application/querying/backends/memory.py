# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Memory vector and direct-text backend adapters for global query."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Application Modules Imports
from brain.application.querying.dtos import GlobalQueryResultDTO, QueryContentDTO
from brain.application.querying.language import find_language_text_matches, language_match_ratio
from brain.application.querying.text_mapping import build_memory_text_result
from brain.application.querying.vector_mapping import wrap_memory_result


def query_memory_backend(text: str, domain: str, limit: int) -> list[GlobalQueryResultDTO]:
    """
    Search the memory vectorstore backend.

    Args:
        text (str): Query text.
        domain (str): Optional memory domain filter.
        limit (int): Maximum memory matches.

    Returns:
        list[GlobalQueryResultDTO]: Normalized memory results.
    """
    try:
        from brain.infrastructure.vectorstores.manager import VectorStoreManager

        manager = VectorStoreManager()
        raw_limit: int = limit * 4 if domain.casefold() != "all" else limit
        memory_matches: list[dict[str, Any]] = manager.search(query=text, limit=raw_limit)
    except Exception as exc:
        return [
            GlobalQueryResultDTO(
                source="memory",
                mechanism="vector",
                kind="warning",
                rank=999.0,
                title="Memory vectorstore unavailable",
                content=QueryContentDTO(title="Memory vectorstore unavailable", excerpt=str(exc)),
                warning=str(exc),
            ),
        ]

    filtered_matches: list[dict[str, Any]] = filter_memory_matches_by_domain(
        matches=memory_matches,
        domain=domain,
    )
    return [
        wrap_memory_result(result=result)
        for result in filtered_matches[:limit]
    ]


def query_memory_text_backend(text: str, domain: str, limit: int) -> list[GlobalQueryResultDTO]:
    """
    Search memory Markdown files with language-aware direct text matching.

    Args:
        text (str): Query text.
        domain (str): Optional memory domain filter.
        limit (int): Maximum text matches.

    Returns:
        list[GlobalQueryResultDTO]: Normalized direct text results.
    """
    try:
        memory_root: Path = get_memory_root()
        root_path: Path = memory_root if domain.casefold() == "all" else resolve_memory_domain(
            memory_root=memory_root,
            domain=domain,
        )
        if not root_path.exists():
            return [
                GlobalQueryResultDTO(
                    source="memory",
                    mechanism="text",
                    kind="warning",
                    rank=999.0,
                    title="Memory domain unavailable",
                    content=QueryContentDTO(
                        title="Memory domain unavailable",
                        excerpt=f"Memory domain folder `{root_path}` does not exist.",
                    ),
                    warning=f"Memory domain folder `{root_path}` does not exist.",
                ),
            ]
    except Exception as exc:
        return [
            GlobalQueryResultDTO(
                source="memory",
                mechanism="text",
                kind="warning",
                rank=999.0,
                title="Memory text search unavailable",
                content=QueryContentDTO(title="Memory text search unavailable", excerpt=str(exc)),
                warning=str(exc),
            ),
        ]

    text_results: list[GlobalQueryResultDTO] = []
    markdown_paths: list[Path] = sorted(root_path.rglob("*.md"))
    for markdown_path in markdown_paths:
        if "vectorstore" in markdown_path.parts:
            continue
        result: GlobalQueryResultDTO | None = match_memory_text_file(
            markdown_path=markdown_path,
            memory_root=memory_root,
            query=text,
        )
        if result is not None:
            text_results.append(result)
        if len(text_results) >= limit:
            break
    return text_results


def get_memory_root() -> Path:
    """Return the memory root using the current process environment."""
    return get_agent_home() / "memory"


def resolve_memory_domain(memory_root: Path, domain: str) -> Path:
    """
    Resolve a dot-notated memory domain under `memory_root`.

    Args:
        memory_root (Path): Runtime memory root.
        domain (str): Dot-notated memory domain.

    Returns:
        Path: Resolved memory domain path.

    Raises:
        ValueError: If a domain segment is invalid.
    """
    parts: list[str] = [
        part.strip()
        for part in domain.split(".")
        if part.strip()
    ]
    if not parts:
        raise ValueError("Memory domain cannot be empty.")
    for part in parts:
        if not all(char.isalnum() or char in "_-" for char in part):
            raise ValueError(f"Invalid memory domain segment `{part}`.")
    return memory_root.joinpath(*parts)


def filter_memory_matches_by_domain(matches: list[dict[str, Any]], domain: str) -> list[dict[str, Any]]:
    """Filter memory vectorstore matches by category prefix."""
    normalized_domain: str = domain.casefold().strip()
    if normalized_domain == "all":
        return matches

    return [
        match
        for match in matches
        if memory_match_belongs_to_domain(match=match, domain=normalized_domain)
    ]


def memory_match_belongs_to_domain(match: dict[str, Any], domain: str) -> bool:
    """Return whether a memory match belongs to the requested domain."""
    category: str = str(match.get("category", "")).casefold()
    return category == domain or category.startswith(f"{domain}.")


def match_memory_text_file(markdown_path: Path, memory_root: Path, query: str) -> GlobalQueryResultDTO | None:
    """
    Return a direct text match for one memory Markdown file.

    Args:
        markdown_path (Path): Markdown file path.
        memory_root (Path): Memory root path.
        query (str): Query text.

    Returns:
        GlobalQueryResultDTO | None: Match result when a fuzzy line match exists.
    """
    try:
        content: str = markdown_path.read_text(encoding="utf-8")
    except Exception:
        return None

    for line_number, line in enumerate(content.splitlines(), 1):
        matches: list[tuple[str, int, int]] = find_language_text_matches(line=line, query=query)
        if not matches:
            continue
        rank: float = 1.0 - max(language_match_ratio(match_text=match[0], query=query) for match in matches)
        return build_memory_text_result(
            markdown_path=markdown_path,
            memory_root=memory_root,
            content=content,
            line=line,
            line_number=line_number,
            matches=matches,
            rank=rank,
        )
    return None
from brain.infrastructure.runtime.paths import get_agent_home
