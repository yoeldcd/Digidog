"""Bounded stdlib JSON parsing with duplicate-key and structure detection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class JsonParseResult:
    """Describe one JSON parse without retaining the parsed source.

    Attributes:
        syntax_valid: Whether stdlib JSON parsing succeeded.
        duplicate_keys: Object keys repeated at any parsed object level.
        value_type: Root JSON value type, or ``None`` after syntax failure.
        object_count: Number of parsed objects.
        array_count: Number of parsed arrays.
        scalar_count: Number of scalar values.
        max_depth: Maximum root-relative nesting depth observed.
        node_count: Number of parsed value nodes.
        structure_valid: Whether configured depth and node limits were respected.
        error_kind: Bounded parse or structure error classification.
        error_line: One-based syntax-error line, when available.
        error_column: One-based syntax-error column, when available.
    """

    syntax_valid: bool
    duplicate_keys: tuple[str, ...]
    value_type: str | None
    object_count: int
    array_count: int
    scalar_count: int
    max_depth: int
    node_count: int
    structure_valid: bool
    error_kind: str | None
    error_line: int | None
    error_column: int | None


class JsonParser:
    """Parse JSON using only the Python standard library with bounded traversal."""

    _DEFAULT_MAX_DEPTH: Final[int] = 100
    _DEFAULT_MAX_NODES: Final[int] = 10000

    def __init__(
        self,
        max_depth: int = _DEFAULT_MAX_DEPTH,
        max_nodes: int = _DEFAULT_MAX_NODES,
    ) -> None:
        """Configure bounded nesting and node limits.

        Args:
            max_depth: Maximum permitted root-relative container depth.
            max_nodes: Maximum permitted parsed value nodes.
        """
        self._max_depth = max(1, max_depth)
        self._max_nodes = max(1, max_nodes)

    def parse(self, content: str) -> JsonParseResult:
        """Parse one JSON string and summarize its structure in memory.

        Args:
            content: Complete JSON source text.

        Returns:
            JsonParseResult: Immutable syntax, duplicate-key, and structure facts.
        """

        if content.startswith("\ufeff"):
            return _invalid_result("bom_not_allowed", 1, 1)

        duplicate_keys: list[str] = []

        def pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
            """Record repeated keys while constructing a normal mapping.

            Args:
                pairs: Object key/value pairs emitted by ``json.loads``.

            Returns:
                dict[str, object]: Mapping containing the last value for each key.
            """
            values: dict[str, object] = {}

            for key, value in pairs:
                if key in values:
                    duplicate_keys.append(key)

                values[key] = value

            return values

        def reject_constant(value: str) -> object:
            """Reject non-standard NaN and Infinity constants.

            Args:
                value: Non-standard constant token supplied by ``json.loads``.

            Returns:
                object: Never returns because the token is invalid.

            Raises:
                ValueError: The token is not valid JSON.
            """

            raise ValueError(f"non-standard JSON constant: {value}")

        try:
            parsed = json.loads(
                content,
                object_pairs_hook=pairs_hook,
                parse_constant=reject_constant,
            )

        except json.JSONDecodeError as error:
            return _invalid_result("invalid_json", error.lineno, error.colno)

        except (RecursionError, ValueError, TypeError):
            return _invalid_result("json_parse_failed", None, None)

        counts = {"object": 0, "array": 0, "scalar": 0, "max_depth": 0, "nodes": 0}
        depth_exceeded = False
        node_exceeded = False

        def visit(value: object, depth: int) -> None:
            """Traverse parsed values until configured bounds are reached.

            Args:
                value: Parsed JSON value currently visited.
                depth: Root-relative nesting depth for the value.

            Returns:
                None: Counts and bound flags are accumulated in the closure.
            """
            nonlocal depth_exceeded, node_exceeded

            if node_exceeded or depth_exceeded:
                return

            counts["nodes"] += 1

            if counts["nodes"] > self._max_nodes:
                node_exceeded = True

                return

            counts["max_depth"] = max(counts["max_depth"], depth)

            if depth > self._max_depth:
                depth_exceeded = True

                return

            if isinstance(value, dict):
                counts["object"] += 1

                for child in value.values():
                    visit(child, depth + 1)

            elif isinstance(value, list):
                counts["array"] += 1

                for child in value:
                    visit(child, depth + 1)

            else:
                counts["scalar"] += 1

        visit(parsed, 0)
        duplicate_tuple = tuple(dict.fromkeys(duplicate_keys))
        structure_valid = (
            not duplicate_tuple and not depth_exceeded and not node_exceeded
        )
        error_kind = None

        if duplicate_tuple:
            error_kind = "duplicate_keys"

        elif depth_exceeded:
            error_kind = "max_depth_exceeded"

        elif node_exceeded:
            error_kind = "max_nodes_exceeded"

        return JsonParseResult(
            syntax_valid=True,
            duplicate_keys=duplicate_tuple,
            value_type=_value_type(parsed),
            object_count=counts["object"],
            array_count=counts["array"],
            scalar_count=counts["scalar"],
            max_depth=counts["max_depth"],
            node_count=min(counts["nodes"], self._max_nodes),
            structure_valid=structure_valid,
            error_kind=error_kind,
            error_line=None,
            error_column=None,
        )


def _invalid_result(
    error_kind: str, line: int | None, column: int | None
) -> JsonParseResult:
    """Build a syntax-invalid result with no source text retained.

    Args:
        error_kind: Bounded parser error classification.
        line: Optional one-based error line.
        column: Optional one-based error column.

    Returns:
        JsonParseResult: Immutable syntax-invalid parse result.
    """

    return JsonParseResult(
        syntax_valid=False,
        duplicate_keys=(),
        value_type=None,
        object_count=0,
        array_count=0,
        scalar_count=0,
        max_depth=0,
        node_count=0,
        structure_valid=False,
        error_kind=error_kind,
        error_line=line,
        error_column=column,
    )


def _value_type(value: object) -> str:
    """Return a stable JSON root type name.

    Args:
        value: Parsed root JSON value.

    Returns:
        str: Stable JSON type identifier.
    """

    if isinstance(value, dict):
        return "object"

    if isinstance(value, list):
        return "array"

    if value is None:
        return "null"

    if isinstance(value, bool):
        return "boolean"

    if isinstance(value, (int, float)):
        return "number"

    return "string"


__all__ = ["JsonParseResult", "JsonParser"]
