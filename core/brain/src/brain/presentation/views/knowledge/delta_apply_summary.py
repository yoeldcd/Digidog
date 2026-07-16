# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Terminal renderers for knowledge delta application summaries."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any


def render_delta_apply_summary(payload: dict[str, Any]) -> list[str]:
    """
    Render a delta application summary as placeholder lines.

    Args:
        payload (dict[str, Any]): Summary payload.

    Returns:
        list[str]: Placeholder-formatted terminal lines.
    """
    message: str = str(payload.get("message") or f"Applied {payload.get('applied', 0)} knowledge deltas.")
    color: str = "__GREEN__" if payload.get("ok", False) else "__YELLOW__"
    lines: list[str] = [f"{color}{message}__RESET__"]
    for error_text in payload.get("errors", []):
        lines.append(f"__YELLOW__{error_text}__RESET__")
    return lines
