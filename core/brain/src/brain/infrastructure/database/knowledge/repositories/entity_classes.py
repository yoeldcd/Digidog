# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Entity class read queries for the SQLite knowledge repository."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any


class KnowledgeEntityClassRepositoryMixin:
    """Read registered entity class definitions."""

    def list_entity_classes(self) -> list[dict[str, Any]]:
        """
        Return registered entity class definitions.

        Returns:
            list[dict[str, Any]]: Entity class rows.
        """
        with self.session() as connection:
            rows = connection.execute(
                "SELECT * FROM entity_classes ORDER BY name",
            ).fetchall()
        return [dict(row) for row in rows]
