"""Public composition and dispatch contract for deterministic analyzers."""

from .dispatcher import AnalyzerDispatcher, AnalyzerRegistry, AnalyzerRegistryError
from .registry import DEFAULT_DISPATCHER, build_default_dispatcher

__all__ = [
    "DEFAULT_DISPATCHER",
    "AnalyzerDispatcher",
    "AnalyzerRegistry",
    "AnalyzerRegistryError",
    "build_default_dispatcher",
]
