# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Schema migration scripts and helpers."""

from brain.infrastructure.database.knowledge.schema.migrations.migrations import migrate_existing_tables

__all__ = ["migrate_existing_tables"]
