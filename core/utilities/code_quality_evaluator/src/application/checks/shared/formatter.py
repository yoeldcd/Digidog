"""Convert in-memory formatter outcomes into deterministic quality gates."""

from __future__ import annotations

from ....domain.models import FormatterSpec, GateResult
from ....infrastructure.formatter_runner import InMemoryFormatterRunner


def check_formatter(
    spec: FormatterSpec,
    content: str,
    path: str,
    runner: InMemoryFormatterRunner | None = None,
) -> GateResult:
    """Run one configured formatter without writing the source file.

    Args:
        spec: Immutable formatter and command specification.
        content: Complete source text held in memory.
        path: Logical workspace-relative source path.
        runner: Optional injected runner used by tests.

    Returns:
        GateResult: Source-redacted formatter status and command evidence.
    """

    formatter_runner = runner or InMemoryFormatterRunner()
    result = formatter_runner.run(
        spec,
        source=content,
        path=path,
    )
    message = (
        "formatter candidate available"
        if result.candidate is not None
        else "formatter candidate unavailable"
    )

    return GateResult(
        gate_id=spec.id,
        status=result.status,
        message=message,
        evidence=result.command_result.evidence,
    )
