"""Language-neutral deterministic analyzer registry and dispatcher."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from ...domain.models import InMemoryFile, Language, LanguageQualityPolicy
from .shared.artifact import evaluate_artifact
from .shared.gate_ids import (
    LANGUAGE_GATE_IDS,
    SHARED_GATE_IDS,
    SUPPORTED_LANGUAGES,
)
from .shared.protocol import AnalyzerResult, BaseLanguageAnalyzer


class AnalyzerRegistryError(ValueError):
    """Report an invalid analyzer registration before any dispatch occurs."""


@dataclass(frozen=True, slots=True)
class AnalyzerRegistry:
    """Own one immutable, total analyzer registry.

    Attributes:
        analyzers: Exactly one analyzer for every supported language, ordered by
            the shared language declaration.
        _by_language: Frozen language-to-analyzer lookup used during dispatch.

    Raises:
        AnalyzerRegistryError: If a language is missing, duplicated, unsupported,
            or declares the wrong gate IDs.
    """

    analyzers: tuple[BaseLanguageAnalyzer, ...]
    _by_language: Mapping[Language, BaseLanguageAnalyzer] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        """Validate and freeze a complete language-to-analyzer mapping.

        Args:
            No arguments are accepted beyond the dataclass instance.

        Returns:
            None: The immutable registry is initialized in place.

        Raises:
            AnalyzerRegistryError: If registration is not total and exact.
        """
        declared = tuple(self.analyzers)

        if len(declared) != len(SUPPORTED_LANGUAGES):
            raise AnalyzerRegistryError("registry must contain six analyzers")

        by_language: dict[Language, BaseLanguageAnalyzer] = {}

        for analyzer in declared:
            if not isinstance(analyzer, BaseLanguageAnalyzer):
                raise AnalyzerRegistryError(
                    "analyzers must specialize BaseLanguageAnalyzer"
                )

            try:
                language = analyzer.language
                gate_ids = tuple(analyzer.gate_ids)
                analyze = analyzer.analyze

            except (AttributeError, TypeError) as error:
                raise AnalyzerRegistryError(
                    "analyzer must expose language, gate_ids, and analyze"
                ) from error

            if not callable(analyze):
                raise AnalyzerRegistryError("analyzer analyze must be callable")

            if language in by_language:
                raise AnalyzerRegistryError(f"duplicate analyzer language: {language}")

            expected_gate_ids = LANGUAGE_GATE_IDS.get(language)

            if expected_gate_ids is None:
                raise AnalyzerRegistryError(
                    f"unsupported analyzer language: {language}"
                )

            if gate_ids != expected_gate_ids:
                raise AnalyzerRegistryError(
                    f"analyzer gate IDs do not match language: {language}"
                )

            by_language[language] = analyzer

        missing_languages = tuple(
            language for language in SUPPORTED_LANGUAGES if language not in by_language
        )

        if missing_languages:
            raise AnalyzerRegistryError(
                f"registry is missing analyzers: {missing_languages}"
            )

        ordered_analyzers = tuple(
            by_language[language] for language in SUPPORTED_LANGUAGES
        )
        object.__setattr__(self, "analyzers", ordered_analyzers)
        object.__setattr__(self, "_by_language", MappingProxyType(by_language))

    @classmethod
    def from_analyzers(
        cls,
        analyzers: Iterable[BaseLanguageAnalyzer],
    ) -> AnalyzerRegistry:
        """Construct a total registry from injected analyzer implementations.

        Args:
            analyzers: One analyzer for each supported language.

        Returns:
            AnalyzerRegistry: Frozen registry ordered by supported language.

        Raises:
            AnalyzerRegistryError: If the supplied collection is not total.
        """

        return cls(tuple(analyzers))

    def for_language(self, language: Language) -> BaseLanguageAnalyzer:
        """Return the registered analyzer for one supported language.

        Args:
            language: Source language selected by the artifact.

        Returns:
            BaseLanguageAnalyzer: Registered analyzer specialization.

        Raises:
            AnalyzerRegistryError: If a caller provides an unsupported language.
        """

        try:
            return self._by_language[language]

        except (KeyError, TypeError) as error:
            raise AnalyzerRegistryError(f"unsupported language: {language}") from error


@dataclass(frozen=True, slots=True)
class AnalyzerDispatcher:
    """Run shared artifact gates and append one exact language gate sequence.

    Attributes:
        registry: Frozen total registry supplying one analyzer per language.
    """

    registry: AnalyzerRegistry

    def dispatch(
        self,
        artifact: InMemoryFile,
        policy: LanguageQualityPolicy | None,
    ) -> AnalyzerResult:
        """Dispatch one artifact entirely in memory.

        Args:
            artifact: Source artifact held in memory, with no filesystem access.
            policy: Exact quality policy for the artifact language.

        Returns:
            AnalyzerResult: Shared artifact gates followed by language gates.

        Raises:
            ValueError: If policy is missing or belongs to another language.
            AnalyzerRegistryError: If the registry cannot resolve the language.
        """

        if policy is None:
            raise ValueError("language policy is required for dispatch")

        if policy.language is not artifact.language:
            raise ValueError("language policy must match artifact language")

        analyzer = self.registry.for_language(artifact.language)
        artifact_gates = evaluate_artifact(
            artifact.path,
            artifact.content,
            artifact.path,
            policy=policy,
        )
        analyzer_result = analyzer.analyze(artifact, policy)

        expected_gate_ids = LANGUAGE_GATE_IDS[artifact.language]

        if analyzer_result.language is not artifact.language:
            raise ValueError("analyzer result language must match artifact language")

        if analyzer_result.gate_ids != expected_gate_ids:
            raise ValueError("analyzer returned an invalid gate sequence")

        combined_gates = (*artifact_gates, *analyzer_result.gates)
        combined_gate_ids = (*SHARED_GATE_IDS, *analyzer_result.gate_ids)

        return AnalyzerResult(
            language=artifact.language,
            gate_ids=combined_gate_ids,
            gates=combined_gates,
        )


def build_analyzer_registry(
    analyzers: Iterable[BaseLanguageAnalyzer],
) -> AnalyzerRegistry:
    """Build a frozen total registry for dependency injection and production use.

    Args:
        analyzers: Analyzer implementations, one for each supported language.

    Returns:
        AnalyzerRegistry: Validated immutable registry.
    """

    return AnalyzerRegistry.from_analyzers(analyzers)


__all__ = [
    "AnalyzerDispatcher",
    "AnalyzerRegistry",
    "AnalyzerRegistryError",
    "build_analyzer_registry",
]
