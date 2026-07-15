"""DTOs for runtime store migration reports."""

from __future__ import annotations

# Third-party Libraries Imports
from pydantic import BaseModel, ConfigDict, Field


class RuntimeMigrationActionDTO(BaseModel):
    """One runtime migration action."""

    model_config = ConfigDict(extra="forbid")

    action: str = Field(...)
    source: str = Field(...)
    target: str = Field(default="")
    detail: str = Field(default="")


class RuntimeMigrationReportDTO(BaseModel):
    """Runtime migration summary."""

    model_config = ConfigDict(extra="forbid")

    actions: list[RuntimeMigrationActionDTO] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
