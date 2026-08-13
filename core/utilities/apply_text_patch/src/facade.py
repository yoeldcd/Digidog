"""Public facade for strict, transactional text patch execution."""

from __future__ import annotations

from pathlib import Path

from .application.input_format import PatchInputFormat, PatchInputFormatError, parse_patch_input
from .application.native_specification import NativePatchSpecificationError
from .application.specification import PatchSpecificationError
from .domain.models import PatchResult
from .infrastructure.engine import FileSystemPatchEngine, PatchExecutionError

__all__ = [
    "PatchExecutionError",
    "PatchSpecificationError",
    "NativePatchSpecificationError",
    "PatchInputFormatError",
    "PatchInputFormat",
    "PatchResult",
    "apply_text_patch",
]


def apply_text_patch(
    serialized_specification: str,
    workspace_root: Path,
    transient_dir: Path,
    check: bool = False,
    input_format: PatchInputFormat = PatchInputFormat.JSON,
) -> PatchResult:
    """Parse and execute one patch request below the trusted workspace root.

    Args:
        serialized_specification: Serialized patch specification in the selected format.
        workspace_root: Physical root that confines all target paths.
        transient_dir: Existing physical directory for owned rollback artifacts.
        check: Validate and plan without writing when true.

    Returns:
        PatchResult: Immutable, source-redacted execution evidence.

    Raises:
        PatchSpecificationError: The JSON specification is invalid.
        NativePatchSpecificationError: The native specification is invalid.
        PatchInputFormatError: The input format cannot be determined safely.
        PatchExecutionError: Planning, execution, or rollback fails.
    """
    request = parse_patch_input(serialized_specification, input_format)
    engine = FileSystemPatchEngine(root=workspace_root, transient_dir=transient_dir)

    return engine.execute(request=request, check=check)
