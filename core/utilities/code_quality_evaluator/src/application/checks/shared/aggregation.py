"""Shared deterministic gate aggregation helpers."""

from __future__ import annotations

import re

from src.domain.models import GateResult


def _natural_gate_key(gate_id: str) -> tuple[tuple[int, object], ...]:
    """Build a stable natural-sort key for a gate identifier.

    Args:
        gate_id: Stable identifier assigned to one gate.

    Returns:
        tuple[tuple[int, object], ...]: Comparable text and numeric key parts.
    """
    parts = re.split(r"(\d+)", gate_id)
    key: list[tuple[int, object]] = []

    for part in parts:
        if part.isdigit():
            key.append((1, int(part)))

        else:
            key.append((0, part))

    return tuple(key)


def aggregate_gates(gates: tuple[GateResult, ...]) -> tuple[GateResult, ...]:
    """Return gates in deterministic natural identifier order and reject duplicates.

    Args:
        gates: Immutable gate results produced by individual checks.

    Returns:
        tuple[GateResult, ...]: Gates sorted by stable natural identifier order.

    Raises:
        ValueError: If two gates share the same identifier.
    """
    seen_gate_ids: set[str] = set()

    for gate in gates:
        if gate.gate_id in seen_gate_ids:
            raise ValueError(f"duplicate gate id: {gate.gate_id}")
        seen_gate_ids.add(gate.gate_id)

    return tuple(sorted(gates, key=lambda gate: _natural_gate_key(gate.gate_id)))
