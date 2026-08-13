"""Select strict patch specification parsers by explicit input format."""

from __future__ import annotations

from enum import StrEnum

from ..domain.models import PatchRequest
from .native_specification import parse_native_patch
from .specification import parse_patch_request


class PatchInputFormat(StrEnum):
    """Identify the parser selected for a patch specification."""

    JSON = "json"
    NATIVE = "native"
    AUTO = "auto"


class PatchInputFormatError(ValueError):
    """Indicate that an input cannot be classified safely."""


def parse_patch_input(
    serialized_specification: str,
    input_format: PatchInputFormat,
) -> PatchRequest:
    """Parse a patch specification using the selected input format.

    Args:
        serialized_specification: Serialized JSON or native patch text.
        input_format: Explicit parser selection, or ``AUTO`` for classification.

    Returns:
        PatchRequest: Parsed immutable patch request from the selected parser.

    Raises:
        PatchInputFormatError: If automatic classification finds no supported format.
        ValueError: Parser-specific exceptions for malformed selected input.
    """

    if input_format is PatchInputFormat.JSON:
        return parse_patch_request(serialized_specification)

    if input_format is PatchInputFormat.NATIVE:
        return parse_native_patch(serialized_specification)

    leading_specification = serialized_specification.lstrip()

    if leading_specification.startswith("{"):
        return parse_patch_request(serialized_specification)

    first_nonblank_line = leading_specification.splitlines()[0] if leading_specification else ""

    if first_nonblank_line == "*** Begin Patch":
        return parse_native_patch(serialized_specification)

    raise PatchInputFormatError("Unable to determine patch input format.")