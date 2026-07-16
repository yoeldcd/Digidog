# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""SQLite knowledge repository composed from focused persistence mixins."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

# Application Modules Imports
from brain.application.knowledge.runtime.config_store import ensure_knowledge_config, ensure_knowledge_root, get_database_path
from brain.application.knowledge.runtime.scopes import get_knowledge_root, get_shared_config_root, normalize_knowledge_scope
from brain.infrastructure.database.knowledge.schema.bootstrap import initialize_schema
from brain.infrastructure.database.knowledge.schema.connection import connect_database
from brain.infrastructure.database.knowledge.repositories.deltas import KnowledgeDeltaRepositoryMixin
from brain.infrastructure.database.knowledge.repositories.entity_aliases import KnowledgeEntityAliasRepositoryMixin
from brain.infrastructure.database.knowledge.repositories.entity_classes import KnowledgeEntityClassRepositoryMixin
from brain.infrastructure.database.knowledge.repositories.entity_lookup import KnowledgeEntityLookupRepositoryMixin
from brain.infrastructure.database.knowledge.repositories.entity_records import KnowledgeEntityRecordsRepositoryMixin
from brain.infrastructure.database.knowledge.repositories.entity_type_assertions import (
    KnowledgeEntityTypeAssertionRepositoryMixin,
)
from brain.infrastructure.database.knowledge.repositories.entity_views import KnowledgeEntityViewRepositoryMixin
from brain.infrastructure.database.knowledge.repositories.ontology import KnowledgeOntologyRepositoryMixin
from brain.infrastructure.database.knowledge.repositories.query import KnowledgeQueryRepositoryMixin
from brain.infrastructure.database.knowledge.repositories.relations import KnowledgeRelationRepositoryMixin
from brain.infrastructure.database.knowledge.repositories.sources import KnowledgeSourceRepositoryMixin


class KnowledgeRepository(
    KnowledgeSourceRepositoryMixin,
    KnowledgeEntityRecordsRepositoryMixin,
    KnowledgeEntityAliasRepositoryMixin,
    KnowledgeEntityLookupRepositoryMixin,
    KnowledgeEntityViewRepositoryMixin,
    KnowledgeEntityClassRepositoryMixin,
    KnowledgeEntityTypeAssertionRepositoryMixin,
    KnowledgeRelationRepositoryMixin,
    KnowledgeDeltaRepositoryMixin,
    KnowledgeOntologyRepositoryMixin,
    KnowledgeQueryRepositoryMixin,
):
    """Persistence boundary for the private knowledge graph."""

    db_path: Path
    """SQLite database path."""

    scope: str
    """Physical knowledge scope served by this repository."""

    def __init__(
        self,
        db_path: Path | None = None,
        knowledge_root: Path | None = None,
        scope: str = "global",
    ) -> None:
        """
        Initialize the repository and ensure schema availability.

        Args:
            db_path (Path | None): Optional database path override.
            knowledge_root (Path | None): Optional runtime knowledge root override.
            scope (str): Physical knowledge scope: `global` or `local`.
        """
        self.scope = normalize_knowledge_scope(scope=scope)
        if db_path is not None:
            self.db_path = db_path
        else:
            resolved_root: Path = knowledge_root or get_knowledge_root(scope=self.scope)
            ensure_knowledge_root(knowledge_root=resolved_root)
            config_dto = ensure_knowledge_config(knowledge_root=get_shared_config_root())
            self.db_path = get_database_path(
                config_dto=config_dto,
                knowledge_root=resolved_root,
                scope=self.scope,
            )
        initialize_schema(db_path=self.db_path)

    def connect(self) -> sqlite3.Connection:
        """
        Open a repository SQLite connection.

        Returns:
            sqlite3.Connection: Configured connection.
        """
        return connect_database(db_path=self.db_path)

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        """
        Open and close a repository SQLite connection.

        Yields:
            sqlite3.Connection: Configured connection.
        """
        connection: sqlite3.Connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    def status(self) -> dict[str, Any]:
        """
        Return database counts and metadata.

        Returns:
            dict[str, Any]: Runtime status payload.
        """
        table_names: tuple[str, ...] = (
            "sources",
            "evidence",
            "entity_classes",
            "entities",
            "entity_type_assertions",
            "aliases",
            "relation_types",
            "relations",
            "ontology_suggestions",
            "pending_deltas",
            "applied_deltas",
            "dream_runs",
        )
        counts: dict[str, int] = {}
        with self.session() as connection:
            for table_name in table_names:
                row = connection.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
                counts[table_name] = int(row["count"])
            version_row = connection.execute(
                "SELECT value FROM schema_meta WHERE key = ?",
                ("schema_version",),
            ).fetchone()
        return {
            "ok": True,
            "scope": self.scope,
            "db_path": self.db_path.as_posix(),
            "schema_version": version_row["value"] if version_row else "unknown",
            "counts": counts,
        }
