# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Pure helpers for knowledge database repositories."""

from __future__ import annotations

# Standard Libraries Imports
import hashlib

# Application Modules Imports
from brain.application.knowledge.models.ontology_keys import normalize_label


def hash_text(text: str) -> str:
    """
    Return a stable SHA-256 digest for text content.

    Args:
        text (str): Source or evidence content.

    Returns:
        str: Hexadecimal SHA-256 digest.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def build_fts_query(text: str) -> str:
    """
    Build a safe FTS5 query from user text.

    Args:
        text (str): Raw search text.

    Returns:
        str: Tokenized FTS5 query.
    """
    tokens: list[str] = [
        token.replace('"', "")
        for token in normalize_label(text).split()
        if token.replace("_", "").replace("-", "").isalnum()
    ]
    if not tokens:
        return '""'
    quoted_tokens: list[str] = [f'"{token}"' for token in tokens[:8]]
    return " OR ".join(quoted_tokens)
