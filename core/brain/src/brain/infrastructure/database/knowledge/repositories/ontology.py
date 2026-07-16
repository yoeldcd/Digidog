# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""KnowledgeOntologyRepositoryMixin for the SQLite knowledge repository."""

from __future__ import annotations

# Standard Libraries Imports
import json
import time
from typing import Any

# Application Modules Imports
from brain.application.knowledge.models.ontology_keys import normalize_label


class KnowledgeOntologyRepositoryMixin:
    def add_schema_suggestion(
        self,
        suggestion_type: str,
        name: str,
        description: str,
        confidence: float,
    ) -> int:
        """
        Insert or reuse an ontology suggestion.

        Args:
            suggestion_type (str): Suggestion kind.
            name (str): Suggested name.
            description (str): Suggested description.
            confidence (float): Suggestion confidence.

        Returns:
            int: Suggestion identifier.
        """
        normalized_name: str = normalize_label(name).replace(" ", "_")
        suggestion_values: tuple[Any, ...] = (
            suggestion_type,
            normalized_name,
            description,
            confidence,
            "pending",
            time.time(),
        )
        with self.session() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO ontology_suggestions(
                    suggestion_type,
                    name,
                    description,
                    confidence,
                    status,
                    created_at
                )
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                suggestion_values,
            )
            row = connection.execute(
                "SELECT id FROM ontology_suggestions WHERE suggestion_type = ? AND name = ?",
                (suggestion_type, normalized_name),
            ).fetchone()
            connection.commit()
        return int(row["id"])

    def ensure_entity_class(self, name: str, description: str = "") -> None:
        """
        Ensure a discovered entity class exists in the ontology registry.

        Args:
            name (str): Entity class key.
            description (str): Optional class description.
        """
        from brain.application.knowledge.models.entity_classes import (
            canonical_class_name,
            canonical_entity_class,
            class_name_from_entity_class,
        )
        from brain.application.knowledge.models.ontology_definitions import CORE_ENTITY_CLASS_DEFINITIONS

        canonical_name: str = canonical_entity_class(name)
        if canonical_name in CORE_ENTITY_CLASS_DEFINITIONS:
            class_name = canonical_name
        else:
            class_name = class_name_from_entity_class(canonical_name) or canonical_class_name(name)
        class_description: str = description or f"Discovered entity class `{class_name}`."
        with self.session() as connection:
            connection.execute(
                """
                INSERT INTO entity_classes(name, description, status, created_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    description = CASE
                        WHEN length(excluded.description) > length(entity_classes.description)
                        THEN excluded.description
                        ELSE entity_classes.description
                    END,
                    status = excluded.status
                """,
                (class_name, class_description, "active", time.time()),
            )
            connection.commit()

    def ensure_relation_type(self, name: str, description: str = "") -> None:
        """
        Ensure a discovered relation type exists in the ontology registry.

        Args:
            name (str): Relation type key.
            description (str): Optional relation description.
        """
        from brain.application.knowledge.models.relation_types import canonical_relation_type

        relation_name: str = canonical_relation_type(name)
        relation_description: str = description or f"Discovered relation type `{relation_name}`."
        with self.session() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO relation_types(name, description, status, created_at)
                VALUES(?, ?, ?, ?)
                """,
                (relation_name, relation_description, "active", time.time()),
            )
            connection.commit()
