# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Pure source path classification rules."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path


def memory_source_type(source_path: str) -> str:
    """
    Classify a memory source path into a source family.

    Args:
        source_path: Stable source path such as `memory/profiles/developer.md`.

    Returns:
        Source type label.
    """
    parts: tuple[str, ...] = tuple(Path(source_path).parts)
    if len(parts) >= 2 and parts[0] == "memory" and parts[1] == "diary":
        return "diary"
    if len(parts) >= 2 and parts[0] == "memory" and parts[1] == "profiles":
        return "profiles"
    return "memory"
