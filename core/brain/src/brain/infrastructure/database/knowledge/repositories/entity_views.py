# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Entity graph read-model accessors for the SQLite knowledge repository."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any


class KnowledgeEntityViewRepositoryMixin:
    """Expose entity graph projections backed by read-model functions."""

    def get_entity(self, entity_ref: int | str) -> dict[str, Any] | None:
        """
        Return an entity with aliases and relations.

        Args:
            entity_ref (int | str): Entity identifier, name, or alias.

        Returns:
            dict[str, Any] | None: Entity graph payload when found.
        """
        from brain.infrastructure.database.knowledge.read_models.entities import get_entity_view

        return get_entity_view(repository=self, entity_ref=entity_ref)

    def list_entities(self) -> list[dict[str, Any]]:
        """
        Return all non-merged entities.

        Returns:
            list[dict[str, Any]]: Entity row payloads.
        """
        from brain.infrastructure.database.knowledge.read_models.entities import list_entity_views

        return list_entity_views(repository=self)
