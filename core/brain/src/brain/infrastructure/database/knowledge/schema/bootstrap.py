"""Schema bootstrap orchestration for the knowledge graph."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3
from pathlib import Path

# Application Modules Imports
from brain.config import KNOWLEDGE_SCHEMA_VERSION
from brain.infrastructure.database.knowledge.schema.connection import connect_database
from brain.infrastructure.database.knowledge.schema.ddl import create_tables
from brain.infrastructure.database.knowledge.schema.fts import create_fts_tables
from brain.infrastructure.database.knowledge.schema.migrations import migrate_existing_tables
from brain.infrastructure.database.knowledge.schema.ontology import (
    prune_unbacked_non_core_ontology,
    seed_core_ontology,
    sync_entity_class_cache_from_cls,
)


def initialize_schema(db_path: Path) -> None:
    """
    Create or migrate the knowledge graph schema.

    Args:
        db_path (Path): SQLite database path.
    """
    connection: sqlite3.Connection = connect_database(db_path=db_path)
    try:
        create_tables(connection=connection)
        migrate_existing_tables(connection=connection)
        create_fts_tables(connection=connection)
        seed_core_ontology(connection=connection)
        sync_entity_class_cache_from_cls(connection=connection)
        prune_unbacked_non_core_ontology(connection=connection)
        connection.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
            ("schema_version", KNOWLEDGE_SCHEMA_VERSION),
        )
        connection.commit()
    finally:
        connection.close()
