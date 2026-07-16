# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Idempotent SQLite migrations for existing knowledge graph stores."""

from __future__ import annotations

# Standard Libraries Imports
import sqlite3

# Application Modules Imports
from brain.infrastructure.database.knowledge.schema.entity_identity_migrations import (
    create_entity_identity_indexes,
    merge_duplicate_entities_by_normalized_name,
)
from brain.infrastructure.database.knowledge.schema.migration_helpers import ensure_column
from brain.infrastructure.database.knowledge.schema.source_migrations import migrate_sources_identity_contract
from brain.infrastructure.database.knowledge.schema.type_assertion_migrations import (
    create_entity_type_assertion_contract,
    seed_entity_type_assertions_from_entities,
)


def migrate_existing_tables(connection: sqlite3.Connection) -> None:
    """
    Migrate databases created by earlier knowledge builds.

    Args:
        connection (sqlite3.Connection): Open SQLite connection.
    """
    migrate_sources_identity_contract(connection=connection)
    ensure_column(
        connection=connection,
        table_name="entities",
        column_name="source_id",
        column_sql="source_id INTEGER",
    )
    ensure_column(
        connection=connection,
        table_name="relations",
        column_name="source_id",
        column_sql="source_id INTEGER",
    )
    create_entity_type_assertion_contract(connection=connection)
    seed_entity_type_assertions_from_entities(connection=connection)
    merge_duplicate_entities_by_normalized_name(connection=connection)
    create_entity_identity_indexes(connection=connection)
