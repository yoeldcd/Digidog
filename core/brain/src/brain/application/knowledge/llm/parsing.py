# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Model output parsers for knowledge LLM stages."""

from __future__ import annotations

# Standard Libraries Imports
import json
import re
from typing import Any

# Application Modules Imports
from brain.config import KNOWLEDGE_MAX_RELATION_EXTRACTION_ITEMS as MAX_RELATION_EXTRACTION_ITEMS


RELATION_TRIPLET_PATTERN = re.compile(
    r'^\s*\(\s*"(?P<subject>(?:[^"\\]|\\.)*)"\s*,\s*'
    r'"(?P<predicate>(?:[^"\\]|\\.)*)"\s*,\s*'
    r'"(?P<object>(?:[^"\\]|\\.)*)"\s*\)\s*$',
)
"""Strict relation triplet line parser for model-authored relation extraction."""


def _parse_model_stage_output(stage_name: str, content_text: str) -> dict[str, Any]:
    """
    Parse a raw model response according to the stage output contract.

    Args:
        stage_name (str): Stage that produced the model output.
        content_text (str): Raw model text.

    Returns:
        dict[str, Any]: Raw delta payload before deterministic sanitization.
    """
    if stage_name == "relation_extraction":
        return _parse_relation_triplet_delta_payload(content_text=content_text)
    return json.loads(_strip_json_fence(content_text))


def _parse_relation_triplet_delta_payload(content_text: str) -> dict[str, Any]:
    """
    Parse compact relation triplet lines into raw relation payloads.

    Args:
        content_text (str): Raw model output with one triplet per line.

    Returns:
        dict[str, Any]: Raw delta payload containing relation name endpoints.

    Raises:
        ValueError: If the output contains non-triplet text.
    """
    stripped_text: str = _strip_text_fence(text=content_text)
    if not stripped_text or stripped_text.casefold() == "none":
        return {"entities": [], "relations": [], "rationale": ""}

    relation_payloads: list[dict[str, Any]] = []
    invalid_lines: list[str] = []
    for raw_line in stripped_text.splitlines():
        line: str = _strip_triplet_line_prefix(line=raw_line)
        if not line:
            continue
        triplet_match = RELATION_TRIPLET_PATTERN.match(line)
        if triplet_match is None:
            invalid_lines.append(raw_line.strip())
            continue
        relation_payloads.append(
            {
                "subject_name": _unescape_triplet_value(triplet_match.group("subject")),
                "predicate": _unescape_triplet_value(triplet_match.group("predicate")),
                "object_name": _unescape_triplet_value(triplet_match.group("object")),
            },
        )
        if len(relation_payloads) >= MAX_RELATION_EXTRACTION_ITEMS:
            break

    if invalid_lines and not relation_payloads:
        raise ValueError(f"relation output must use triplet lines; invalid line: {invalid_lines[0]}")
    return {
        "entities": [],
        "relations": relation_payloads,
        "rationale": "triplet relation extraction",
    }


def _strip_triplet_line_prefix(line: str) -> str:
    """
    Remove harmless list prefixes before parsing a relation triplet.

    Args:
        line (str): Raw output line.

    Returns:
        str: Candidate triplet line.
    """
    stripped_line: str = line.strip()
    if stripped_line.startswith("- "):
        stripped_line = stripped_line[2:].strip()
    return re.sub(r"^\d+[\.)]\s*", "", stripped_line)


def _unescape_triplet_value(value: str) -> str:
    """
    Decode JSON-style escaping inside a quoted triplet value.

    Args:
        value (str): Raw captured string value without surrounding quotes.

    Returns:
        str: Unescaped value.
    """
    try:
        decoded_value = json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value.replace('\\"', '"').replace("\\\\", "\\")
    return str(decoded_value)


def _strip_json_fence(text: str) -> str:
    """
    Remove Markdown code fences around JSON text.

    Args:
        text (str): Raw model text.

    Returns:
        str: JSON string candidate.
    """
    stripped_text: str = text.strip()
    if stripped_text.startswith("```"):
        stripped_text = stripped_text.strip("`")
        if stripped_text.startswith("json"):
            stripped_text = stripped_text[4:]
    return stripped_text.strip()


def _strip_text_fence(text: str) -> str:
    """
    Remove Markdown code fences around plain text output.

    Args:
        text (str): Raw model text.

    Returns:
        str: Plain text candidate.
    """
    stripped_text: str = text.strip()
    if not stripped_text.startswith("```"):
        return stripped_text
    stripped_text = stripped_text.strip("`").strip()
    first_line, _, remaining_text = stripped_text.partition("\n")
    if first_line and not first_line.strip().startswith("(") and first_line.strip().casefold() != "none":
        return remaining_text.strip()
    return stripped_text
