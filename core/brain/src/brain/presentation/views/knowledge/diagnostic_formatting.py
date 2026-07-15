"""Terminal formatting primitives for live knowledge diagnostics."""

from __future__ import annotations

# Standard Libraries Imports
from typing import Any


def join_delta_ids(delta_ids: list[int]) -> str:
    """
    Join delta IDs for terminal display.

    Args:
        delta_ids (list[int]): Delta identifiers.

    Returns:
        str: Comma-separated identifiers.
    """
    return ",".join(str(delta_id) for delta_id in delta_ids)


def counts_text(counts: dict[str, int]) -> str:
    """
    Render compact KG metric counts.

    Args:
        counts (dict[str, int]): Entity, relation, alias, and schema counts.

    Returns:
        str: Human-readable metric summary.
    """
    return (
        f"Et {number(counts.get('Et', 0))}  "
        f"Re {number(counts.get('Re', 0))}  "
        f"Ale {number(counts.get('Ale', 0))}  "
        f"Sch {number(counts.get('Sch', 0))}"
    )


def field(value: str) -> str:
    """
    Render a diagnostic field label.

    Args:
        value (str): Field label.

    Returns:
        str: Placeholder field label.
    """
    return f"__DIM__{value}:__RESET__"


def schema_text(value: Any) -> str:
    """
    Render a stage or schema-like token.

    Args:
        value (Any): Raw token.

    Returns:
        str: Placeholder schema token.
    """
    return f"__MAGENTA__{clean_inline_text(value=value)}__RESET__"


def number(value: Any) -> str:
    """
    Render a numeric diagnostic value.

    Args:
        value (Any): Raw value.

    Returns:
        str: Placeholder numeric value.
    """
    return f"__CYAN__{value}__RESET__"


def live_text(value: Any) -> str:
    """
    Render live source, prompt, or model output text.

    Args:
        value (Any): Raw text.

    Returns:
        str: Blue quoted placeholder text.
    """
    clean_text: str = clean_inline_text(value=value)
    escaped_text: str = clean_text.replace('"', '\\"')
    return f"__BLUE__\"{escaped_text}\"__RESET__"


def clean_inline_text(value: Any) -> str:
    """
    Normalize text for one-line terminal output.

    Args:
        value (Any): Raw value.

    Returns:
        str: Single-line text.
    """
    return " ".join(str(value or "").split())
