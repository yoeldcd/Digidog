"""Immutable change-operation contracts used by agent-directory catalogs."""

# Standard library imports
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ChangeOperationStrategy(str, Enum):
    """Identify the deterministic strategy used by one catalog operation.

    Members:
        COPY: Copy a source resource into the destination.
        REPLACE: Replace an existing destination with a source resource.
        MERGE: Merge source content into an existing destination.
        RENDER: Render a template into the destination.
        EXCLUDE: A file or directory excluded when COPY it parent.
    """

    COPY = "copy"
    REPLACE = "replace"
    MERGE = "merge"
    RENDER = "render"
    EXCLUDE = "exclude"


@dataclass(frozen=True)
class ChangeOperationDTO:
    """Describe one immutable, root-scoped file operation without performing I/O.

    Attributes:
        source: Relative source resource identity (file or directory); empty only for rendering.
        target: Safe non-empty relative destination path.
        strategy: Operation strategy controlling source/template requirements.
        ownership_root: Relative catalog root used by the composition boundary.
        template: Template identifier required only by render operations.
        remove_stale: Whether stale destination removal is explicitly permitted.
    """

    source: Path
    """Relative source resource identity; empty only for rendering."""

    target: Path
    """Safe non-empty relative destination path."""

    strategy: ChangeOperationStrategy
    """Strategy controlling source and template requirements."""

    ownership_root: Path = Path(".")
    """Relative catalog root supplied by the composition boundary."""

    template: str | None = None
    """Template identifier required only by render operations."""

    remove_stale: bool = False
    """Explicit stale-destination removal policy."""

    def __post_init__(self) -> None:
        """Validate operation invariants and reject unsafe or incomplete contracts.

        Raises:
            ValueError: If paths are absolute/traversal-based or strategy inputs
                violate the source/template contract.
        """

        if self.target.is_absolute() or self.target.anchor or ".." in self.target.parts or not self.target.parts:
            raise ValueError("target must be a safe relative path")

        if self.ownership_root.is_absolute() or self.ownership_root.anchor or ".." in self.ownership_root.parts:
            raise ValueError("ownership_root must be a safe relative path")

        if self.strategy is ChangeOperationStrategy.RENDER and not self.template:
            raise ValueError("render operations require a template")

        if self.strategy is not ChangeOperationStrategy.RENDER and self.template is not None:
            raise ValueError("template is only valid for render operations")

        if self.strategy is ChangeOperationStrategy.RENDER and self.source.parts:
            raise ValueError("render operations must not provide a source")

        if self.strategy is not ChangeOperationStrategy.RENDER and (
            self.source.is_absolute()
            or self.source.anchor
            or ".." in self.source.parts
            or not self.source.parts
        ):
            raise ValueError("source must be a safe relative path")

        if self.strategy is ChangeOperationStrategy.EXCLUDE:
            if (
                (self.source.is_absolute() or self.source.anchor)
                or ".." in self.source.parts
                or not self.source.parts
            ):
                raise ValueError("exclude operations require a safe relative source")
            if self.remove_stale:
                raise ValueError("exclude operations must not remove stale destinations")
            return

        if self.strategy is not ChangeOperationStrategy.RENDER and not self.source.parts:
            raise ValueError("source is required for non-render operations")
