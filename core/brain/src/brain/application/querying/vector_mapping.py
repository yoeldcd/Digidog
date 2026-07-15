"""Memory vectorstore result mapping into global query DTOs."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.application.querying.dtos import GlobalQueryResultDTO, QueryContentDTO, QuerySourceRefDTO
from brain.application.querying.source_refs import source_ref_from_path, source_type_from_memory_path
from brain.application.querying.text_mapping import compact_excerpt


def wrap_memory_result(result: dict[str, Any]) -> GlobalQueryResultDTO:
    """
    Convert one memory vectorstore match into the global query DTO.

    Args:
        result (dict[str, Any]): Vectorstore match.

    Returns:
        GlobalQueryResultDTO: Normalized result.
    """
    metadata: dict[str, Any] = dict(result.get("metadata") or {})
    title: str = str(
        metadata.get("entry_title")
        or result.get("title")
        or result.get("key")
        or result.get("id")
        or "",
    )
    similarity: float = float(result.get("similarity", 0.0))
    text: str = display_text_from_vector_result(result=result, metadata=metadata)
    source_ref: QuerySourceRefDTO = source_ref_from_memory_vector_result(result=result)
    return GlobalQueryResultDTO(
        source="memory",
        mechanism="vector",
        kind="vector_memory",
        rank=1.0 - similarity,
        title=title,
        text=text,
        data=dict(result),
        content=QueryContentDTO(
            title=title,
            excerpt=compact_excerpt(text=text, limit=900),
            body=text,
        ),
        source_ref=source_ref,
    )


def source_ref_from_memory_vector_result(result: dict[str, Any]) -> QuerySourceRefDTO:
    """Build a source reference for one vector memory result."""
    category: str = str(result.get("category") or result.get("metadata", {}).get("category") or "").strip()
    key: str = str(result.get("key") or result.get("metadata", {}).get("key") or "").strip()
    path: str = str(result.get("path") or result.get("metadata", {}).get("path") or "").strip()
    metadata: dict[str, Any] = dict(result.get("metadata") or {})
    if not path and category and key:
        path = f"memory/{category.replace('.', '/')}/{key}.md"
    elif path and not path.startswith("memory/") and not path.startswith("$agent/"):
        path = f"memory/{path.lstrip('/')}"
    source_ref: QuerySourceRefDTO = source_ref_from_path(
        path=path,
        source_type=source_type_from_memory_path(path.replace("memory/", "", 1)),
        title=str(result.get("title") or ""),
        scope="global",
        entry_time=str(metadata.get("entry_time") or ""),
        entry_title=str(metadata.get("entry_title") or ""),
    )
    read_command: str = str(metadata.get("read_command") or "")
    if read_command:
        return source_ref.model_copy(update={"read_command": read_command})
    return source_ref


def display_text_from_vector_result(result: dict[str, Any], metadata: dict[str, Any]) -> str:
    """Return body text for a vector result without repeating navigational metadata."""
    body_text: str = str(metadata.get("body") or "").strip()
    if body_text:
        return body_text
    return strip_leading_markdown_heading(text=str(result.get("text", "")))


def strip_leading_markdown_heading(text: str) -> str:
    """Remove the first heading line from legacy vector chunks."""
    lines: list[str] = text.splitlines()
    if lines and lines[0].lstrip().startswith("#"):
        return "\n".join(lines[1:]).strip()
    return text.strip()
