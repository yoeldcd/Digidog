# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Knowledge search entrypoint for the SQLite knowledge repository."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any


class KnowledgeQueryRepositoryMixin:
    def search(self, text: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Search entities and evidence through SQLite FTS5.

        Args:
            text (str): Search query.
            limit (int): Maximum result count.

        Returns:
            list[dict[str, Any]]: Ranked result payloads.
        """
        from brain.infrastructure.database.knowledge.read_models.search import search_repository

        return search_repository(repository=self, text=text, limit=limit)
