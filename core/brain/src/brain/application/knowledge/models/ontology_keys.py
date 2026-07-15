"""Shared ontology key normalization helpers."""

from __future__ import annotations

# Standard Libraries Imports
import re


def normalize_label(value: str) -> str:
    """
    Normalize a label for matching and deduplication.

    Args:
        value (str): Raw label text from a source or LLM proposal.

    Returns:
        str: Case-folded label with compact whitespace.
    """
    compact_value: str = re.sub(r"\s+", " ", value.strip())
    return compact_value.casefold()


def normalize_ontology_key(value: str) -> str:
    """
    Normalize arbitrary ontology labels into snake_case keys.

    Args:
        value (str): Raw ontology key or natural-language label.

    Returns:
        str: Lower snake_case ontology key.
    """
    normalized_value: str = normalize_label(value)
    normalized_value = re.sub(r"[^a-z0-9]+", "_", normalized_value)
    normalized_value = re.sub(r"_+", "_", normalized_value).strip("_")
    if normalized_value and not normalized_value[0].isalpha():
        normalized_value = f"k_{normalized_value}"
    return normalized_value[:64]


def is_valid_ontology_key(value: str) -> bool:
    """
    Validate a dynamic ontology key.

    Args:
        value (str): Candidate normalized ontology key.

    Returns:
        bool: True when the key is a safe snake_case identifier.
    """
    return bool(re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value))
