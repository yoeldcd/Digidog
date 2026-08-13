"""Strict, Unicode-safe JSON parsing for guarded patch requests."""

from __future__ import annotations

import json
from pathlib import PureWindowsPath

from ..domain.models import (
    CreateSpec,
    DeleteSpec,
    EditSpec,
    MoveSpec,
    PatchRequest,
    ReplacementSpec,
)


class PatchSpecificationError(ValueError):
    """Indicate an invalid patch request before filesystem access occurs."""


def parse_patch_request(serialized_specification: str) -> PatchRequest:
    """Parse a strict JSON patch request before filesystem access.

    Args:
        serialized_specification: Complete standard-input JSON document.

    Returns:
        PatchRequest: Immutable, validated patch declarations.

    Raises:
        PatchSpecificationError: If JSON syntax, Unicode, field types, or duplicate
            targets fail validation.
    """

    _validate_unicode(serialized_specification, "patch specification")
    if not serialized_specification.strip():
        raise PatchSpecificationError(
            "apply-patch requires one JSON specification on standard input.",
        )

    try:
        parsed_value: object = json.loads(serialized_specification)
    except json.JSONDecodeError as exc:
        raise PatchSpecificationError("Patch specification must be valid JSON.") from exc

    if not isinstance(parsed_value, dict):
        raise PatchSpecificationError("Patch specification must be a JSON object.")

    _reject_unknown_fields(
        parsed_value,
        {"edits", "creates", "moves", "deletes"},
        "patch specification",
    )
    edits = _parse_edits(parsed_value.get("edits", []))
    creates = _parse_creates(parsed_value.get("creates", []))
    moves = _parse_moves(parsed_value.get("moves", []))
    deletes = _parse_deletes(parsed_value.get("deletes", []))

    if not edits and not creates and not moves and not deletes:
        raise PatchSpecificationError(
            "Patch specification requires at least one edit, create, move, or delete.",
        )

    target_keys = (
        tuple(_target_key(item.path) for item in edits)
        + tuple(_target_key(item.path) for item in creates)
        + tuple(_target_key(item.from_path) for item in moves)
        + tuple(_target_key(item.to_path) for item in moves)
        + tuple(_target_key(item.path) for item in deletes)
    )
    
    if len(set(target_keys)) != len(target_keys):
        raise PatchSpecificationError(
            "Each normalized patch target path must be declared exactly once.",
        )

    return PatchRequest(edits=edits, creates=creates, moves=moves, deletes=deletes)


def _parse_edits(value: object) -> tuple[EditSpec, ...]:
    """Parse immutable edit declarations.

    Args:
        value: Raw edits array from JSON object.

    Returns:
        tuple[EditSpec, ...]: Immutable tuple of EditSpec instances.

    Raises:
        PatchSpecificationError: If edits format or replacements are invalid.
    """

    if not isinstance(value, list):
        raise PatchSpecificationError("edits must be an array.")

    parsed_edits: list[EditSpec] = []
    for index, raw_edit in enumerate(value):
        location = f"edits[{index}]"
        
        if not isinstance(raw_edit, dict):
            raise PatchSpecificationError(f"{location} must be an object.")

        _reject_unknown_fields(
            raw_edit,
            {"path", "replacements", "allowEmptyResult"},
            location,
        )
        path = _required_path(raw_edit, "path", location)
        replacements_value: object = raw_edit.get("replacements")

        if not isinstance(replacements_value, list) or not replacements_value:
            raise PatchSpecificationError(
                f"{location}.replacements must be a non-empty array.",
            )

        replacements = tuple(
            _parse_replacement(raw_replacement, location, replacement_index)
            for replacement_index, raw_replacement in enumerate(replacements_value)
        )
        allow_empty_result = _optional_boolean(raw_edit, location)
        parsed_edits.append(EditSpec(path, replacements, allow_empty_result))

    return tuple(parsed_edits)


def _parse_creates(value: object) -> tuple[CreateSpec, ...]:
    """Parse immutable create declarations.

    Args:
        value: Raw creates array from JSON object.

    Returns:
        tuple[CreateSpec, ...]: Immutable tuple of CreateSpec instances.

    Raises:
        PatchSpecificationError: If creates format or content is invalid.
    """

    if not isinstance(value, list):
        raise PatchSpecificationError("creates must be an array.")

    parsed_creates: list[CreateSpec] = []
    
    for index, raw_create in enumerate(value):
        location = f"creates[{index}]"
        
        if not isinstance(raw_create, dict):
            raise PatchSpecificationError(f"{location} must be an object.")

        _reject_unknown_fields(
            raw_create,
            {"path", "content", "allowEmptyResult"},
            location,
        )
        path = _required_path(raw_create, "path", location)
        content: object = raw_create.get("content")

        if not isinstance(content, str):
            raise PatchSpecificationError(f"{location}.content must be a string.")

        _validate_unicode(content, f"{location}.content")
        allow_empty_result = _optional_boolean(raw_create, location)

        if not content and not allow_empty_result:
            raise PatchSpecificationError(
                f"{location}.content is empty; set allowEmptyResult to true to permit it.",
            )

        parsed_creates.append(CreateSpec(path, content, allow_empty_result))

    return tuple(parsed_creates)


def _parse_moves(value: object) -> tuple[MoveSpec, ...]:
    """Parse immutable move declarations.

    Args:
        value: Raw moves array from JSON object.

    Returns:
        tuple[MoveSpec, ...]: Immutable tuple of MoveSpec instances.

    Raises:
        PatchSpecificationError: If move paths are invalid or non-distinct.
    """
    
    if not isinstance(value, list):
        raise PatchSpecificationError("moves must be an array.")

    parsed_moves: list[MoveSpec] = []

    for index, raw_move in enumerate(value):
        location = f"moves[{index}]"
        if not isinstance(raw_move, dict):
            raise PatchSpecificationError(f"{location} must be an object.")

        _reject_unknown_fields(
            raw_move,
            {"fromPath", "toPath"},
            location,
        )

        from_path = _required_path(raw_move, "fromPath", location)
        to_path = _required_path(raw_move, "toPath", location)

        if _target_key(from_path) == _target_key(to_path):
            raise PatchSpecificationError(
                f"{location} fromPath and toPath must be distinct targets.",
            )

        parsed_moves.append(MoveSpec(from_path=from_path, to_path=to_path))

    return tuple(parsed_moves)


def _parse_deletes(value: object) -> tuple[DeleteSpec, ...]:
    """Parse immutable delete declarations.

    Args:
        value: Raw deletes array from JSON object.

    Returns:
        tuple[DeleteSpec, ...]: Immutable tuple of DeleteSpec instances.

    Raises:
        PatchSpecificationError: If deletes format or path is invalid.
    """

    if not isinstance(value, list):
        raise PatchSpecificationError("deletes must be an array.")

    parsed_deletes: list[DeleteSpec] = []
    
    for index, raw_delete in enumerate(value):
        location = f"deletes[{index}]"
        if not isinstance(raw_delete, dict):
            raise PatchSpecificationError(f"{location} must be an object.")

        _reject_unknown_fields(
            raw_delete,
            {"path"},
            location,
        )
        path = _required_path(raw_delete, "path", location)
        parsed_deletes.append(DeleteSpec(path=path))

    return tuple(parsed_deletes)


def _parse_replacement(
    raw_value: object,
    edit_location: str,
    index: int,
) -> ReplacementSpec:
    """Parse one exact replacement declaration.

    Args:
        raw_value: Raw replacement dict from JSON.
        edit_location: Location label of parent edit.
        index: Index of replacement within array.

    Returns:
        ReplacementSpec: Validated exact replacement specification.

    Raises:
        PatchSpecificationError: If fields are missing, invalid, or no-op.
    """

    location = f"{edit_location}.replacements[{index}]"
    
    if not isinstance(raw_value, dict):
        raise PatchSpecificationError(f"{location} must be an object.")

    _reject_unknown_fields(
        raw_value,
        {"old", "new", "expectedOccurrences"},
        location,
    )
    old: object = raw_value.get("old")
    new: object = raw_value.get("new")
    expected_occurrences: object = raw_value.get("expectedOccurrences", 1)

    if not isinstance(old, str) or not old:
        raise PatchSpecificationError(f"{location}.old must be a non-empty string.")
    
    if not isinstance(new, str):
        raise PatchSpecificationError(f"{location}.new must be a string.")

    _validate_unicode(old, f"{location}.old")
    _validate_unicode(new, f"{location}.new")

    if isinstance(expected_occurrences, bool):
        raise PatchSpecificationError(
            f"{location}.expectedOccurrences must be a positive integer.",
        )
    if not isinstance(expected_occurrences, int) or expected_occurrences <= 0:
        raise PatchSpecificationError(
            f"{location}.expectedOccurrences must be a positive integer.",
        )
    if old == new:
        raise PatchSpecificationError(f"{location} is a semantic no-op.")

    return ReplacementSpec(old, new, expected_occurrences)


def _required_path(raw_value: dict[str, object], field_name: str, location: str) -> str:
    """Read one required Unicode-safe target path.

    Args:
        raw_value: Parent dict containing the field.
        field_name: Name of target path field.
        location: Context location for error messages.

    Returns:
        str: Validated non-empty string path.

    Raises:
        PatchSpecificationError: If path is missing, empty, or has bad Unicode.
    """

    path: object = raw_value.get(field_name)

    if not isinstance(path, str) or not path.strip():
        raise PatchSpecificationError(f"{location}.{field_name} must be a non-empty string.")

    _validate_unicode(path, f"{location}.{field_name}")

    return path


def _optional_boolean(raw_value: dict[str, object], location: str) -> bool:
    """Read an optional strict boolean opt-in.

    Args:
        raw_value: Parent dict containing the optional field.
        location: Context location for error messages.

    Returns:
        bool: Parsed boolean value, defaulting to False.

    Raises:
        PatchSpecificationError: If provided value is not a boolean.
    """

    if "allowEmptyResult" not in raw_value:
        return False

    value: object = raw_value["allowEmptyResult"]

    if not isinstance(value, bool):
        raise PatchSpecificationError(
            f"{location}.allowEmptyResult must be a boolean.",
        )

    return value


def _target_key(path: str) -> str:
    """Return the Windows-safe duplicate detection key for one declared target.

    Args:
        path: Workspace relative target path.

    Returns:
        str: Normalized, case-folded path key.
    """

    normalized = path.replace(chr(92), "/")
    parts = tuple(part for part in PureWindowsPath(normalized).parts if part != ".")

    return "/".join(parts).casefold()


def _validate_unicode(value: str, location: str) -> None:
    """Reject text that cannot be strictly encoded as UTF-8.

    Args:
        value: Text value to check.
        location: Context location for error messages.

    Raises:
        PatchSpecificationError: If text fails strict UTF-8 encoding.
    """

    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise PatchSpecificationError(f"{location} contains invalid Unicode.") from exc


def _reject_unknown_fields(
    raw_value: dict[str, object],
    allowed_fields: set[str],
    location: str,
) -> None:
    """Reject fields outside one exact public JSON object schema.

    Args:
        raw_value: Dict to validate.
        allowed_fields: Set of recognized field names.
        location: Context location for error messages.

    Raises:
        PatchSpecificationError: If unknown fields are found.
    """

    unknown_fields = sorted(set(raw_value) - allowed_fields)
    
    if unknown_fields:
        joined_fields = ", ".join(unknown_fields)
        raise PatchSpecificationError(
            f"{location} contains unknown field(s): {joined_fields}.",
        )