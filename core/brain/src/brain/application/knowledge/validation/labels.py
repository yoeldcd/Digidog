"""Label-shape validation rules for knowledge deltas."""

from __future__ import annotations

# Standard Libraries Imports
import re


TRAILING_DESCRIPTOR_ADJECTIVES: set[str] = {
    "actual",
    "anterior",
    "current",
    "digital",
    "global",
    "legacy",
    "local",
    "new",
    "nuevo",
    "old",
    "original",
    "previous",
    "viejo",
}
"""Descriptor adjectives that belong in descriptions when they trail a proper label."""

DOCUMENT_STRUCTURE_LABEL_PATTERN = re.compile(
    r"^(diary|log|memory|source|document|entry|section)\s*[-:]\s*\d{2}-\d{2}-\d{4}$",
    re.IGNORECASE,
)
"""Document wrapper labels that describe source structure rather than content."""


def is_document_structure_label(label: str) -> bool:
    """
    Return whether a label names a source wrapper rather than content.

    Args:
        label (str): Candidate canonical name.

    Returns:
        bool: True when the label is source metadata.
    """
    return DOCUMENT_STRUCTURE_LABEL_PATTERN.match(label.strip()) is not None


def has_trailing_descriptor_adjective(label: str) -> bool:
    """
    Return whether a proper label ends with a non-signature descriptor adjective.

    Args:
        label (str): Candidate canonical name.

    Returns:
        bool: True when the adjective should move to the description.
    """
    words: list[str] = re.findall(r"[A-Za-zÀ-ÿ0-9_]+", label)
    if len(words) != 2:
        return False
    first_word, second_word = words
    if not first_word[:1].isupper():
        return False
    return second_word.casefold() in TRAILING_DESCRIPTOR_ADJECTIVES


def is_sentence_like_label(label: str) -> bool:
    """
    Return whether an entity label looks like copied prose instead of a compact object label.

    Args:
        label (str): Candidate canonical name.

    Returns:
        bool: True when the label should be rejected as sentence-like text.
    """
    if is_technical_artifact_label(label=label):
        return False
    if len(label) > 72:
        return True
    words: list[str] = re.findall(r"[A-Za-z0-9_]+", label)
    if len(words) > 8:
        return True
    if re.search(r"[;!?]", label):
        return True
    if ":" in label and len(words) > 2:
        return True
    if label.endswith("."):
        return True
    lowered_label: str = label.casefold()
    sentence_starts: tuple[str, ...] = (
        "always ",
        "never ",
        "do not ",
        "must ",
        "use this ",
        "the system ",
        "the kg ",
    )
    return any(lowered_label.startswith(prefix) for prefix in sentence_starts)


def is_technical_artifact_label(label: str) -> bool:
    """
    Return whether a compact label looks like a file, module, or package artifact.

    Args:
        label (str): Candidate canonical name.

    Returns:
        bool: True when punctuation is part of a technical identifier rather than prose.
    """
    if " " in label:
        return False
    if re.fullmatch(r"[A-Za-z]:\\[^\s]+", label):
        return True
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._@+$/-]*", label):
        return False
    return bool(re.search(r"\.[A-Za-z0-9][A-Za-z0-9_-]*$", label))


def normalize_key_fragment(value: str) -> str:
    """
    Normalize a label into the same fragment style used by ontology keys.

    Args:
        value (str): Raw label text.

    Returns:
        str: Lower snake_case fragment.
    """
    normalized_value: str = re.sub(r"[^a-z0-9]+", "_", value.casefold())
    return re.sub(r"_+", "_", normalized_value).strip("_")
