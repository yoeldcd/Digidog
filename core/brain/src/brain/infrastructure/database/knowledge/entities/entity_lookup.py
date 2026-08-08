# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Entity lookup queries for the SQLite knowledge repository."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.application.knowledge.models.ontology_keys import normalize_label


class KnowledgeEntityLookupRepositoryMixin:
    """Find active entities by class, identifier, canonical name, or alias."""

    def find_entity(self, entity_class: str, canonical_name: str) -> dict[str, Any] | None:
        """
        Find an active entity by canonical name and one asserted class.

        Args:
            entity_class (str): Entity class key.
            canonical_name (str): Canonical entity name.

        Returns:
            dict[str, Any] | None: Entity row when found.
        """
        normalized_name: str = normalize_label(canonical_name)
        with self.session() as connection:
            row = connection.execute(
                """
                SELECT entities.*
                FROM entities
                WHERE entities.normalized_name = ?
                    AND entities.status != 'merged'
                    AND (
                        entities.entity_class = ?
                        OR EXISTS (
                            SELECT 1
                            FROM entity_type_assertions
                            WHERE entity_type_assertions.entity_id = entities.id
                                AND entity_type_assertions.entity_class = ?
                                AND entity_type_assertions.status != 'rejected'
                        )
                    )
                ORDER BY entities.confidence DESC, entities.id ASC
                LIMIT 1
                """,
                (normalized_name, entity_class, entity_class),
            ).fetchone()
        return dict(row) if row else None

    def find_entity_by_ref(self, entity_ref: int | str) -> dict[str, Any] | None:
        """
        Find an entity by ID, canonical name, or alias.

        Args:
            entity_ref (int | str): Entity identifier or label.

        Returns:
            dict[str, Any] | None: Entity row when found.
        """
        with self.session() as connection:
            if isinstance(entity_ref, int):
                row = connection.execute("SELECT * FROM entities WHERE id = ?", (entity_ref,)).fetchone()
                if row and str(row["status"]) == "merged" and row["merged_into_id"] is not None:
                    row = connection.execute(
                        "SELECT * FROM entities WHERE id = ?",
                        (int(row["merged_into_id"]),),
                    ).fetchone()
                return dict(row) if row else None

            normalized_ref: str = normalize_label(entity_ref)
            row = connection.execute(
                "SELECT * FROM entities WHERE normalized_name = ? AND status != 'merged' ORDER BY confidence DESC",
                (normalized_ref,),
            ).fetchone()
            if row:
                return dict(row)
            alias_row = connection.execute(
                """
                SELECT entities.*
                FROM aliases
                JOIN entities ON entities.id = aliases.entity_id
                WHERE aliases.normalized_alias = ? AND entities.status != 'merged'
                ORDER BY entities.confidence DESC
                """,
                (normalized_ref,),
            ).fetchone()
        return dict(alias_row) if alias_row else None
