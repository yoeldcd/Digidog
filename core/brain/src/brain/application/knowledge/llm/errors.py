# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Errors raised by knowledge LLM stages."""

from __future__ import annotations


class KnowledgeLLMError(RuntimeError):
    """Raised when a model-backed knowledge stage cannot complete."""
