# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Entity alias mutations for the SQLite knowledge repository."""

from __future__ import annotations

# Standard Libraries Imports
import time

# Application Modules Imports
from brain.application.knowledge.models.ontology_keys import normalize_label


class KnowledgeEntityAliasRepositoryMixin:
    """Persist alternate labels attached to canonical entities."""

    def add_alias(self, entity_id: int, alias: str) -> int:
        """
        Insert or reuse an alias for an entity.

        Args:
            entity_id (int): Target entity identifier.
            alias (str): Alias label.

        Returns:
            int: Alias database identifier.
        """
        normalized_alias: str = normalize_label(alias)
        with self.session() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO aliases(entity_id, alias, normalized_alias, created_at)
                VALUES(?, ?, ?, ?)
                """,
                (entity_id, alias, normalized_alias, time.time()),
            )
            row = connection.execute(
                "SELECT id FROM aliases WHERE entity_id = ? AND normalized_alias = ?",
                (entity_id, normalized_alias),
            ).fetchone()
            connection.commit()
        return int(row["id"])
