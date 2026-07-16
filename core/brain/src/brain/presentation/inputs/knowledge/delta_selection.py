# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Interactive delta selection for knowledge dream review."""

from __future__ import annotations

# Standard Libraries Imports
import sys
from typing import Any

# Application Modules Imports
from brain.application.knowledge.pipeline.delta_status import is_delta_applicable
from brain.presentation.terminal import render_placeholders


def prompt_delta_selection(rows: list[dict[str, Any]], color_enabled: bool) -> list[dict[str, Any]]:
    """
    Ask the user which applicable deltas should be applied.

    Args:
        rows (list[dict[str, Any]]): Pending delta review rows.
        color_enabled (bool): Whether ANSI color placeholders should render.

    Returns:
        list[dict[str, Any]]: Selected rows to apply.
    """
    applicable_delta_ids: set[int] = {
        int(row["id"])
        for row in rows
        if is_delta_applicable(row=row)
    }
    if not applicable_delta_ids:
        return []
    if not sys.stdin.isatty():
        print(
            render_placeholders(
                "__YELLOW__Interactive confirmation is unavailable; proposals remain pending.__RESET__",
                color_enabled,
            ),
        )
        return []

    while True:
        answer = input("Apply deltas? Type y for all, n for none, or delta IDs like 48,52: ").strip()
        try:
            selected_delta_ids = parse_delta_selection(
                answer=answer,
                applicable_delta_ids=applicable_delta_ids,
            )
            return [
                row
                for row in rows
                if int(row["id"]) in selected_delta_ids
            ]
        except ValueError as exc:
            print(render_placeholders(f"__RED__{exc}__RESET__", color_enabled))


def parse_delta_selection(answer: str, applicable_delta_ids: set[int]) -> set[int]:
    """
    Parse a y/n/subset response from the dream confirmation prompt using displayed delta IDs.

    Args:
        answer (str): Raw user response.
        applicable_delta_ids (set[int]): Persisted delta IDs that can be applied.

    Returns:
        set[int]: Selected delta IDs.

    Raises:
        ValueError: If the response does not match y, n, or a valid number list.
    """
    normalized_answer: str = answer.casefold().strip()
    if normalized_answer in ("y", "yes"):
        return set(applicable_delta_ids)
    if normalized_answer in ("n", "no"):
        return set()
    if not normalized_answer:
        raise ValueError("Choose y, n, or a comma-separated list of delta numbers.")

    selected_delta_ids: set[int] = set()
    for raw_part in normalized_answer.split(","):
        part: str = raw_part.strip()
        if not part.isdigit():
            raise ValueError(f"Invalid delta selection `{raw_part}`.")
        selected_delta_ids.add(int(part))

    blocked_delta_ids: set[int] = selected_delta_ids - applicable_delta_ids
    if blocked_delta_ids:
        blocked_text = ", ".join(str(delta_id) for delta_id in sorted(blocked_delta_ids))
        raise ValueError(f"Delta IDs not displayed or not applicable: {blocked_text}.")
    return selected_delta_ids
