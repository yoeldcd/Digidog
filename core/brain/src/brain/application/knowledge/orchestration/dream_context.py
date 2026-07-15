"""Read-only context builders for dream LLM stages."""

from __future__ import annotations

# Application Modules Imports
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository


def build_graph_context(repository: KnowledgeRepository, limit: int = 20) -> str:
    """
    Build a compact read-only context snapshot for model-backed stages.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        limit (int): Maximum entities and relations to include.

    Returns:
        str: Plain-text graph context for LLM prompts.
    """
    status_payload: dict = repository.status()
    entities: list[dict] = repository.list_entities()[:limit]
    relations: list[dict] = repository.list_relations()[:limit]
    entity_lines: list[str] = [f"- {row['entity_class']}: \"{row['canonical_name']}\"" for row in entities]
    relation_lines: list[str] = [
        (
            f"- \"{row.get('subject_name')}\" "
            f"{row['predicate']} \"{row.get('object_name')}\""
        )
        for row in relations
    ]
    return "\n".join(
        [
            f"Counts: {status_payload['counts']}",
            "Entities:",
            *entity_lines,
            "Relations:",
            *relation_lines,
        ],
    )


def build_entity_resolution_context(repository: KnowledgeRepository, limit: int = 500) -> dict[str, int]:
    """
    Build a hidden exact-name resolver for persisted graph entities.

    Args:
        repository (KnowledgeRepository): Knowledge repository.
        limit (int): Maximum persisted entities to expose to the resolver.

    Returns:
        dict[str, int]: Canonical entity names mapped to persisted entity IDs.
    """
    entities: list[dict] = repository.list_entities()[:limit]
    return {str(row["canonical_name"]): int(row["id"]) for row in entities}
