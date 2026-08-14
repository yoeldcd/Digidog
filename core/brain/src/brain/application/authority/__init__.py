"""Authority application package for Brain CLI security enforcement."""

from __future__ import annotations

from brain.application.authority.memory_guard import is_memory_access_allowed
from brain.application.authority.models import BrainAuthoritySpec
from brain.application.authority.service import AuthorityService

__all__ = [
    "BrainAuthoritySpec",
    "AuthorityService",
    "is_memory_access_allowed",
]

