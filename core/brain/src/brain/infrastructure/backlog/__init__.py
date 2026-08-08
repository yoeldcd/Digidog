"""Infrastructure adapters for workspace-explicit task management."""

from brain.infrastructure.backlog.attachments import CanonicalPngAttachmentStore
from brain.infrastructure.backlog.catalog import JsonRegisteredProjectCatalog

__all__ = ["CanonicalPngAttachmentStore", "JsonRegisteredProjectCatalog"]