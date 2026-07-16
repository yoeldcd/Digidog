# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""JSON-LD export view for the knowledge graph."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any

# Application Modules Imports
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository


def export_jsonld(repository: KnowledgeRepository) -> dict[str, Any]:
    """
    Export the knowledge graph as compact JSON-LD.

    Args:
        repository (KnowledgeRepository): Knowledge repository.

    Returns:
        dict[str, Any]: JSON-LD graph payload.
    """
    entities: list[dict[str, Any]] = repository.list_entities()
    relations: list[dict[str, Any]] = repository.list_relations()
    graph_items: list[dict[str, Any]] = []

    for entity in entities:
        graph_items.append(
            {
                "@id": f"entity:{entity['id']}",
                "@type": entity["entity_class"],
                "name": entity["canonical_name"],
                "description": entity["description"],
                "source": {"@id": f"source:{entity['source_id']}"} if entity.get("source_id") else None,
                "confidence": entity["confidence"],
            },
        )

    for relation in relations:
        graph_items.append(
            {
                "@id": f"relation:{relation['id']}",
                "@type": "Relation",
                "source": {"@id": f"source:{relation['source_id']}"},
                "subject": {"@id": f"entity:{relation['subject_entity_id']}"},
                "predicate": relation["predicate"],
                "object": {"@id": f"entity:{relation['object_entity_id']}"},
                "confidence": relation["confidence"],
            },
        )

    return {
        "@context": {
            "name": "https://schema.org/name",
            "description": "https://schema.org/description",
            "confidence": "https://knowledge.local/kg/confidence",
            "predicate": "https://knowledge.local/kg/predicate",
            "source": "https://knowledge.local/kg/source",
            "subject": "https://knowledge.local/kg/subject",
            "object": "https://knowledge.local/kg/object",
        },
        "@graph": graph_items,
    }
