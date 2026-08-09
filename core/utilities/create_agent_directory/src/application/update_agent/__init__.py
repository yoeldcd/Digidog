"""Public application boundary for updating an existing agent directory.

The package exports immutable request/result values and the dependency-injected
use case; implementation details remain private to :mod:`.use_case`.
"""
from .use_case import UpdateAgentInput, UpdateAgentResult, UpdateAgentUseCase

__all__ = ["UpdateAgentInput", "UpdateAgentResult", "UpdateAgentUseCase"]
