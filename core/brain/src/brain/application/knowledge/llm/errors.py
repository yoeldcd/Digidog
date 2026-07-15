"""Errors raised by knowledge LLM stages."""

from __future__ import annotations


class KnowledgeLLMError(RuntimeError):
    """Raised when a model-backed knowledge stage cannot complete."""
