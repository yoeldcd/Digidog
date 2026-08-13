"""Pure recursive JSON missing-key normalization."""
from collections.abc import Mapping
from typing import Any

def normalize_missing_keys(source: Mapping[str, Any], target: Mapping[str, Any]) -> dict[str, Any]:
    """Return target-complete JSON without mutating either mapping.

    Args:
        source: Default values mapping.
        target: Existing values mapping, always taking precedence.
    Returns:
        dict[str, Any]: Deep-copied merged mapping.
    """

    result: dict[str, Any] = {}

    for key, value in source.items():
        if key not in target:
            result[key] = _clone(value)
        elif isinstance(value, Mapping) and isinstance(target[key], Mapping):
            result[key] = normalize_missing_keys(value, target[key])

    for key, value in target.items():
        if key not in source or not (isinstance(source[key], Mapping) and isinstance(value, Mapping)):
            result[key] = _clone(value)

    return result


def _clone(value: Any) -> Any:
    """Clone JSON-compatible values recursively."""

    if isinstance(value, Mapping):
        return {key: _clone(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_clone(item) for item in value]

    return value
