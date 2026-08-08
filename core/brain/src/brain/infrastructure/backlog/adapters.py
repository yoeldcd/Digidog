"""Compatibility imports for task-manager infrastructure adapters."""

from brain.infrastructure.backlog.attachments import CanonicalPngAttachmentStore
from brain.infrastructure.backlog.catalog import JsonRegisteredProjectCatalog

__all__ = ["CanonicalPngAttachmentStore", "JsonRegisteredProjectCatalog"]