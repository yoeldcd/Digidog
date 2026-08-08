# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""DTOs for runtime store migration reports."""

from __future__ import annotations

# Third-party Libraries Imports
from pydantic import BaseModel, ConfigDict, Field


class RuntimeMigrationActionDTO(BaseModel):
    """One runtime migration action.

    Attributes:
        action (str): Migration operation classification.
        source (str): Original runtime path.
        target (str): Optional destination path.
        detail (str): Human-readable action detail.
    """

    model_config = ConfigDict(extra="forbid")

    action: str = Field(...)
    source: str = Field(...)
    target: str = Field(default="")
    detail: str = Field(default="")


class RuntimeMigrationReportDTO(BaseModel):
    """Runtime migration summary.

    Attributes:
        actions (list[RuntimeMigrationActionDTO]): Completed migration actions.
        warnings (list[str]): Non-blocking migration warnings.
    """

    model_config = ConfigDict(extra="forbid")

    actions: list[RuntimeMigrationActionDTO] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
