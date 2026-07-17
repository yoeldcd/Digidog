# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Search services for the knowledge graph."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path
from typing import Any

# Application Modules Imports
from brain.infrastructure.runtime.paths import get_vectorstore_dir

from brain.infrastructure.database.knowledge.repository import KnowledgeRepository


def query_knowledge(
    repository: KnowledgeRepository,
    text: str,
    limit: int = 10,
    hybrid: bool = False,
) -> list[dict[str, Any]]:
    """
    Search the knowledge graph with optional vectorstore fallback.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        text (str): Query text.
        limit (int): Maximum result count.
        hybrid (bool): Whether to include ChromaDB memory matches.

    Returns:
        list[dict[str, Any]]: Combined search results.
    """
    results: list[dict[str, Any]] = repository.search(text=text, limit=limit)
    if not hybrid:
        return results

    try:
        from brain.infrastructure.vectorstores.manager import VectorStoreManager

        vectorstore_path: Path = get_vectorstore_dir(scope="global")
        manager = VectorStoreManager(db_path=vectorstore_path, collection_name="memories")
        try:
            vector_matches: list[dict] = manager.search(query=text, limit=max(1, limit // 2))
        finally:
            close_manager = getattr(manager, "close", None)
            if callable(close_manager):
                close_manager()
        for match in vector_matches:
            results.append(
                {
                    "kind": "vector_memory",
                    "rank": 1.0 - float(match.get("similarity", 0.0)),
                    "data": match,
                },
            )
    except Exception as exc:
        results.append(
            {
                "kind": "hybrid_warning",
                "rank": 999.0,
                "data": {"warning": str(exc)},
            },
        )

    results.sort(key=lambda item: float(item["rank"]))
    return results[:limit]
