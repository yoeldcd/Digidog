# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Formatting helpers for global query terminal views."""

from __future__ import annotations


def format_confidence(confidence: float) -> str:
    """
    Format a compact confidence value.

    Args:
        confidence (float): Confidence score.

    Returns:
        str: Compact confidence string.
    """
    if confidence >= 0.995:
        return "1"
    return f"{confidence:.2f}".lstrip("0")


def compact_excerpt(text: str, limit: int = 220) -> str:
    """
    Return a single-line excerpt for detailed terminal output.

    Args:
        text (str): Raw result body.
        limit (int): Maximum excerpt length.

    Returns:
        str: Compact excerpt.
    """
    compact_text: str = "\n".join(
        " ".join(line.split())
        for line in text.splitlines()
        if line.strip()
    )
    return compact_text[:limit]
