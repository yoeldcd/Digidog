"""Immutable contracts implemented by every language analyzer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import model_validator
from src.domain.models import (
    DTO,
    GateResult,
    InMemoryFile,
    Language,
    LanguageQualityPolicy,
)


class AnalyzerContractError(ValueError):
    """Report a language analyzer result that violates its fixed gate contract."""


class AnalyzerResult(DTO):
    """Represent one immutable, strictly validated analyzer result.

    Attributes:
        language: Language whose analyzer produced the gates.
        gate_ids: Exact declared identifiers for the gates.
        gates: Exactly the declared gates in declaration order.

    Raises:
        AnalyzerContractError: If cardinality, identifiers, or ordering differ
            from the shared declaration.
    """

    language: Language
    gate_ids: tuple[str, ...]
    gates: tuple[GateResult, ...]

    @model_validator(mode="after")
    def validate_gate_contract(self) -> AnalyzerResult:
        """Validate exact gate cardinality, identifiers, and declaration order.

        Args:
            No arguments are accepted beyond the model instance.

        Returns:
            AnalyzerResult: This validated immutable result.

        Raises:
            AnalyzerContractError: If the produced gate sequence is not exact.
        """
        actual_gate_ids = tuple(gate.gate_id for gate in self.gates)

        if actual_gate_ids != self.gate_ids:
            raise AnalyzerContractError(
                "analyzer gates must match the declared IDs and order"
            )

        if len(set(self.gate_ids)) != len(self.gate_ids):
            raise AnalyzerContractError("analyzer gate IDs must be unique")

        return self


class BaseLanguageAnalyzer(ABC):
    """Own the invariant execution contract shared by language analyzers.

    Attributes:
        language: Source language implemented by the specialization.
        gate_ids: Exact gate declaration emitted by the specialization.
    """

    language: ClassVar[Language]
    gate_ids: ClassVar[tuple[str, ...]]

    def analyze(
        self,
        artifact: InMemoryFile,
        policy: LanguageQualityPolicy,
    ) -> AnalyzerResult:
        """Validate shared invariants and execute the specialized analyzer.

        Args:
            artifact: Source artifact held entirely in memory.
            policy: Complete quality policy for the artifact language.

        Returns:
            AnalyzerResult: Exact language gate sequence in declaration order.

        Raises:
            AnalyzerContractError: The artifact, policy, or specialization result
                violates the fixed language contract.
        """

        if artifact.language is not self.language:
            raise AnalyzerContractError("artifact language must match analyzer")

        if policy.language is not self.language:
            raise AnalyzerContractError("policy language must match analyzer")

        gates = tuple(self._analyze(artifact, policy))

        return AnalyzerResult(
            language=self.language,
            gate_ids=self.gate_ids,
            gates=gates,
        )

    @abstractmethod
    def _analyze(
        self,
        artifact: InMemoryFile,
        policy: LanguageQualityPolicy,
    ) -> tuple[GateResult, ...]:
        """Return the language-specific gate sequence.

        Args:
            artifact: Source artifact held entirely in memory.
            policy: Complete policy for the analyzer language.

        Returns:
            tuple[GateResult, ...]: Gates in the declared fixed order.

        Raises:
            NotImplementedError: This abstract contract has no default implementation.
        """

        raise NotImplementedError


__all__ = ["AnalyzerContractError", "AnalyzerResult", "BaseLanguageAnalyzer"]
