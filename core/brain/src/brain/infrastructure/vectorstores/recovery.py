"""Vectorstore recovery and refresh decision helpers."""

from __future__ import annotations

# Application Modules Imports
from brain.config import EMBEDDING_UNAVAILABLE_MARKERS, VECTORSTORE_RETRY_COMMAND


def is_embedding_unavailable_error(error: object) -> bool:
    """
    Return True when an exception looks like an embedding service failure.

    Args:
        error: Exception or error-like object.

    Returns:
        bool: Whether the message indicates unavailable embeddings.
    """
    message = str(error).lower()
    return any(marker in message for marker in EMBEDDING_UNAVAILABLE_MARKERS)


def embedding_unavailable_guide(command: str | None = VECTORSTORE_RETRY_COMMAND) -> str:
    """
    Build a user-facing guide for recovering from embedding failures.

    Args:
        command: Optional command to include as retry guidance.

    Returns:
        str: Renderable CLI guidance text.
    """
    command_line = f"\n  Retry with elevated permissions: {command}" if command else ""
    return (
        "__YELLOW__Embedding model unavailable.__RESET__"
        f"{command_line}"
    )


def requires_entry_metadata_refresh(category: str, metadata: dict | None) -> bool:
    """
    Return whether an indexed vector chunk predates entry-level metadata.

    Args:
        category: Memory category.
        metadata: Existing vector metadata.

    Returns:
        bool: True when the source should be reindexed.
    """
    if not (category == "diary" or category.startswith("diary.")):
        return False
    if not metadata:
        return True
    return not all(metadata.get(field) for field in ("entry_title", "entry_time", "read_command", "body"))
