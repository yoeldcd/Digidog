# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Relation type normalization helpers for the knowledge graph."""

from __future__ import annotations

# Application Modules Imports
from brain.application.knowledge.models.ontology_keys import is_valid_ontology_key, normalize_ontology_key


def is_relation_type_allowed(predicate: str) -> bool:
    """
    Check whether a relation predicate key can be used by the discovered ontology.

    Args:
        predicate (str): Candidate relation predicate.

    Returns:
        bool: True when the predicate key is syntactically valid.
    """
    return is_valid_ontology_key(canonical_relation_type(predicate))


def canonical_relation_type(predicate: str) -> str:
    """
    Return the canonical relation type key.

    Args:
        predicate (str): Raw predicate string.

    Returns:
        str: Canonical snake_case relation key.
    """
    normalized_predicate: str = normalize_ontology_key(predicate)
    if not normalized_predicate:
        return "related_to"
    return normalized_predicate
