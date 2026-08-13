"""Parse contextual native patch specifications into immutable domain models."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Final

from ..domain.models import (
    CreateSpec,
    DeleteSpec,
    EditSpec,
    MoveSpec,
    PatchRequest,
    ReplacementSpec,
)


BEGIN_SENTINEL: Final[str] = "*** Begin Patch"
"""Sentinel required at the start of a valid native patch document."""

END_SENTINEL: Final[str] = "*** End Patch"
"""Sentinel required at the end of a valid native patch document."""

MOVE_DIRECTIVE: Final[str] = "*** Move to:"
"""Directive prefix indicating target relocation during an update."""

END_OF_FILE_MARKER: Final[str] = "*** End of File"
"""Marker constraining the preceding native hunk to the file boundary."""

DIRECTIVE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\*\*\* (Add|Delete|Update) File: (.+)",
)
"""Regex pattern matching directive headers."""


class NativePatchSpecificationError(ValueError):
    """Represent a malformed native patch specification."""


@dataclass(frozen=True, slots=True)
class _Section:
    """Represent one parsed patch directive and its immutable body.

    Attributes:
        operation: Operation name (Add, Delete, or Update).
        path: Target relative path.
        destination: Optional target destination path for move relocations.
        content_lines: Raw content lines inside the directive section.
    """

    operation: str
    path: str
    destination: str | None
    content_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ParsedHunk:
    """Represent one native hunk before conversion to a replacement."""

    lines: tuple[str, ...]
    end_of_file: bool


def parse_native_patch(serialized_specification: str) -> PatchRequest:
    """Parse a contextual native patch into an immutable request.

    Args:
        serialized_specification: Complete native patch text.

    Returns:
        PatchRequest: Immutable parsed operations in declaration order.

    Raises:
        NativePatchSpecificationError: The document, directive, path, or hunk is invalid.
    """
    
    _validate_unicode(serialized_specification)
    normalized, terminal_newline = _normalize_document(serialized_specification)
    body = _extract_body(normalized)
    sections = _parse_sections(body)

    if not sections:
        raise NativePatchSpecificationError("Patch contains no directives.")

    return _build_request(sections=sections, terminal_newline=terminal_newline)


def _validate_unicode(serialized_specification: str) -> None:
    """Reject empty or invalid-Unicode patch text.

    Args:
        serialized_specification: Raw input specification text.

    Raises:
        NativePatchSpecificationError: If input is empty or contains bad Unicode.
    """

    if not serialized_specification:
        raise NativePatchSpecificationError("Patch specification is empty.")

    try:
        serialized_specification.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise NativePatchSpecificationError("Invalid Unicode in patch specification.") from error


def _normalize_document(serialized_specification: str) -> tuple[str, bool]:
    """Normalize line separators and report whether the document ended in one.

    Args:
        serialized_specification: Raw input specification text.

    Returns:
        tuple[str, bool]: Normalized text with LF line endings and terminal newline flag.
    """

    normalized = serialized_specification.replace("\r\n", "\n").replace("\r", "\n")
    terminal_newline = normalized.endswith("\n")

    return normalized, terminal_newline


def _extract_body(normalized: str) -> list[str]:
    """Validate outer sentinels and return directive lines.

    Args:
        normalized: Document text with normalized line endings.

    Returns:
        list[str]: Directive body lines excluding sentinels.

    Raises:
        NativePatchSpecificationError: If sentinels are missing or invalid.
    """

    lines = normalized.split("\n")
    if normalized.endswith("\n"):
        lines = lines[:-1]

    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()

    valid_sentinels = (
        len(lines) >= 2
        and lines[0] == BEGIN_SENTINEL
        and lines[-1] == END_SENTINEL
    )
    if not valid_sentinels:
        raise NativePatchSpecificationError("Invalid patch sentinels.")

    return lines[1:-1]


def _parse_sections(body: list[str]) -> tuple[_Section, ...]:
    """Parse directive headers and bodies into immutable sections.

    Args:
        body: Directive lines extracted from the document.

    Returns:
        tuple[_Section, ...]: Parsed directive sections.

    Raises:
        NativePatchSpecificationError: If directive syntax or ordering is invalid.
    """

    sections: list[_Section] = []
    index = 0

    while index < len(body):
        directive_match = DIRECTIVE_PATTERN.fullmatch(body[index])
        
        if directive_match is None:
            raise NativePatchSpecificationError("Unknown directive or stray content.")

        operation = directive_match.group(1)
        path = _parse_path(directive_match.group(2))
        index += 1
        destination: str | None = None

        if index < len(body) and body[index].startswith(MOVE_DIRECTIVE):
            if operation != "Update":
                raise NativePatchSpecificationError("Move directive placement is invalid.")

            raw_destination = body[index][len(MOVE_DIRECTIVE):].lstrip()
            destination = _parse_path(raw_destination)
            index += 1

        content_lines: list[str] = []

        while index < len(body):
            current_line = body[index]

            if current_line == END_OF_FILE_MARKER:
                content_lines.append(current_line)
                index += 1
                continue

            if current_line.startswith("*** "):
                break

            content_lines.append(current_line)
            index += 1

        section = _Section(
            operation=operation,
            path=path,
            destination=destination,
            content_lines=tuple(content_lines),
        )
        sections.append(section)

    return tuple(sections)


def _build_request(
    sections: tuple[_Section, ...],
    terminal_newline: bool,
) -> PatchRequest:
    """Convert parsed sections into immutable patch operations.

    Args:
        sections: Parsed directive sections.
        terminal_newline: Whether the document ends with a newline.

    Returns:
        PatchRequest: Immutable patch request populated with operations.

    Raises:
        NativePatchSpecificationError: If path conflicts or section errors occur.
    """

    owned_paths: set[str] = set()
    edits: list[EditSpec] = []
    creates: list[CreateSpec] = []
    moves: list[MoveSpec] = []
    deletes: list[DeleteSpec] = []

    for section in sections:
        _claim_path(section.path, owned_paths)
    
        if section.destination is not None:
            _claim_path(section.destination, owned_paths)

        if section.operation == "Add":
            content = _parse_add(section.content_lines, terminal_newline)
            creates.append(CreateSpec(section.path, content, False))
            continue

        if section.operation == "Delete":
            if section.content_lines:
                raise NativePatchSpecificationError("Delete directive cannot contain a body.")
            deletes.append(DeleteSpec(section.path))
            continue

        if section.destination is not None and not section.content_lines:
            moves.append(MoveSpec(section.path, section.destination))
            continue

        replacements = _parse_hunks(section.content_lines)
        edits.append(
            EditSpec(
                path=section.path,
                replacements=replacements,
                allow_empty_result=False,
                destination_path=section.destination,
            )
        )

    return PatchRequest(
        edits=tuple(edits),
        creates=tuple(creates),
        moves=tuple(moves),
        deletes=tuple(deletes),
    )


def _claim_path(path: str, owned_paths: set[str]) -> None:
    """Reserve one normalized path exactly once.

    Args:
        path: Path string to declare.
        owned_paths: Set tracking previously claimed normalized paths.

    Raises:
        NativePatchSpecificationError: If path is already owned.
    """
    
    key = path.replace("\\", "/").casefold()
    
    if key in owned_paths:
        raise NativePatchSpecificationError("Conflicting path ownership.")

    owned_paths.add(key)


def _parse_add(lines: tuple[str, ...], terminal_newline: bool) -> str:
    """Parse an add body and preserve deterministic newline semantics.

    Args:
        lines: Content lines belonging to an Add directive.
        terminal_newline: Whether input document ended with a newline.

    Returns:
        str: Final text content for the created file.

    Raises:
        NativePatchSpecificationError: If add lines do not start with '+'.
    """
    
    if not lines or any(not line.startswith("+") for line in lines):
        raise NativePatchSpecificationError("Invalid add body.")

    content = "\n".join(line[1:] for line in lines)
    
    if terminal_newline:
        content += "\n"
    
    if not content:
        raise NativePatchSpecificationError("Add content cannot be empty.")

    return content


def _parse_hunks(
    lines: tuple[str, ...],
) -> tuple[ReplacementSpec, ...]:
    """Parse ordered update hunks into exact replacement specifications.

    Args:
        lines: Content lines belonging to an Update directive body.
    Returns:
        tuple[ReplacementSpec, ...]: Immutable replacement specifications.

    Raises:
        NativePatchSpecificationError: If hunk syntax or structure is invalid.
    """
    
    groups: list[_ParsedHunk] = []
    current: list[str] | None = None
    current_ends_at_file = False

    for line in lines:
    
        if line.startswith("@@"):
            if current is not None:
                groups.append(
                    _ParsedHunk(tuple(current), end_of_file=current_ends_at_file)
                )
            header_context = line[2:].strip()
            current = [f" {header_context}"] if header_context else []
            current_ends_at_file = False
            continue

        if line == END_OF_FILE_MARKER:
            if current is None or current_ends_at_file:
                raise NativePatchSpecificationError("Invalid end-of-file marker.")

            current_ends_at_file = True
            continue

        valid_hunk_line = current is not None and bool(line) and line[0] in " +-"
        if not valid_hunk_line:
            raise NativePatchSpecificationError("Invalid hunk line.")

        current.append(line)

    if current is not None:
        groups.append(_ParsedHunk(tuple(current), end_of_file=current_ends_at_file))
    
    if not groups:
        raise NativePatchSpecificationError("Patch update contains no hunks.")

    replacements = tuple(
        _replacement_from_hunk(group=group)
        for group in groups
    )

    return replacements


def _replacement_from_hunk(
    group: _ParsedHunk,
) -> ReplacementSpec:
    """Convert one validated hunk group into an exact replacement.

    Args:
        group: Parsed lines and file-boundary constraint for one hunk.
    Returns:
        ReplacementSpec: Exact replacement specification.

    Raises:
        NativePatchSpecificationError: If hunk content is empty or unchanged.
    """

    old = "\n".join(line[1:] for line in group.lines if line[0] in " -")
    new = "\n".join(line[1:] for line in group.lines if line[0] in " +")
    contains_change = any(line[0] in "+-" for line in group.lines)

    if old == new or not contains_change:
        raise NativePatchSpecificationError("Invalid hunk content.")

    return ReplacementSpec(
        old=old,
        new=new,
        expected_occurrences=1,
        contextual=True,
        end_of_file=group.end_of_file,
    )


def _parse_path(path: str) -> str:
    """Validate and return a strict workspace-relative path.

    Args:
        path: Raw path string from directive header.

    Returns:
        str: Validated relative path.

    Raises:
        NativePatchSpecificationError: If path is absolute, empty, or contains traversal.
    """

    invalid_root = path.startswith(("/", "\\")) or bool(PureWindowsPath(path).drive)
    
    if not path or path.strip() != path or invalid_root:
        raise NativePatchSpecificationError("Invalid relative path.")

    parts = path.replace("\\", "/").split("/")
    
    if any(part in ("", ".", "..") for part in parts):
        raise NativePatchSpecificationError("Invalid relative path.")

    return path
