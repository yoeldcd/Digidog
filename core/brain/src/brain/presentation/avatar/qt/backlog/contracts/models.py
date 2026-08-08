"""Typed view and theme models for the Qt task manager."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TaskStatus(StrEnum):
    """Lifecycle states exposed by the backlog view."""

    TODO = "TODO"
    WORKING = "WORKING"
    DONE = "DONE"


class TaskPriority(StrEnum):
    """Priority levels rendered by the backlog view."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True, slots=True)
class BacklogThemeTokens:
    """Contrast-safe tokens inherited from the avatar theme mode.

    Attributes:
        mode: Theme identifier selected by the avatar window.
        background: Main window background color.
        surface: Primary panel surface color.
        surface_alt: Secondary surface color for controls and groups.
        text: Primary readable foreground color.
        muted: Secondary text and metadata color.
        border: Structural border color.
        accent: Primary action and selection color.
        accent_hover: Hover color for accent controls.
        accent_text: Readable foreground color over accent backgrounds.
        selected: Background color for selected backlog items.
    """

    mode: str
    background: str
    surface: str
    surface_alt: str
    text: str
    muted: str
    border: str
    accent: str
    accent_hover: str
    accent_text: str
    selected: str


@dataclass(frozen=True, slots=True)
class ProjectView:
    """Project identity presented in the project selector.

    Attributes:
        key: Stable workspace identifier used by application callbacks.
        label: Human-readable project name shown in the selector.
    """

    key: str
    label: str


@dataclass(frozen=True, slots=True)
class TaskView:
    """Backlog task projection consumed by the Qt list and detail views.

    Attributes:
        task_id: Stable task identifier from the consumer backlog.
        project: Workspace key owning the task.
        domain: Hierarchical task domain.
        title: Short task title displayed in list rows.
        description: Markdown-capable task description.
        priority: Serialized priority label.
        status: Current lifecycle state.
        created_at: Creation timestamp used for ordering.
    """

    task_id: str
    project: str
    domain: str
    title: str
    description: str
    priority: str
    status: TaskStatus
    created_at: float = 0.0


@dataclass(frozen=True, slots=True)
class TaskEditSource:
    """Immutable raw task data consumed only by the edit form."""

    project: str
    task_id: str
    domain: str
    title: str
    raw_description: str
    priority: str
    reference_png: bytes | None = None


@dataclass(frozen=True, slots=True)
class TaskEnrichmentDraft:
    """Immutable values sent to the unsaved task-description enrichment port.

    Attributes:
        domain: Hierarchical task domain currently entered in the form.
        title: Current task title entered in the form.
        priority: Current task priority selected in the form.
        description: Current Markdown-capable task description.
        reference_png: Optional in-memory PNG attachment captured in the form.
    """

    domain: str
    title: str
    priority: str
    description: str
    reference_png: bytes | None = None


@dataclass(frozen=True, slots=True)
class TaskEnrichmentResult:
    """Immutable description proposal returned by the enrichment port.

    Attributes:
        description: Generated Markdown that may replace the current description.
    """

    description: str


@dataclass(frozen=True, slots=True)
class NewTaskDraft:
    """User-entered values used to create one backlog task.

    Attributes:
        project: Workspace key receiving the new task.
        domain: Hierarchical domain selected by the user.
        title: Short task title.
        description: Markdown-capable task description.
        priority: Requested priority label.
        screenshot_png: Optional annotated PNG attachment.
    """

    project: str
    domain: str
    title: str
    description: str
    priority: str
    screenshot_png: bytes | None = None


@dataclass(frozen=True, slots=True)
class EditTaskDraft:
    """Allowed edits for one task in its selected project.

    Attributes:
        project: Workspace key owning the selected task.
        task_id: Stable identifier of the task being edited.
        domain: Optional replacement domain.
        title: Optional replacement title.
        description: Optional replacement Markdown description.
        priority: Optional replacement priority.
        screenshot_png: Optional replacement annotated PNG attachment.
    """

    project: str
    task_id: str
    domain: str | None = None
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    screenshot_png: bytes | None = None


def backlog_theme(mode: str) -> BacklogThemeTokens:
    """Return one complete palette for the requested avatar theme mode.

    Args:
        mode: Avatar theme name; unsupported values use the light palette.

    Returns:
        BacklogThemeTokens: Complete colors used by the backlog presentation.
    """
    if mode == "dark":
        return BacklogThemeTokens(
            mode="dark",
            background="#171418",
            surface="#242025",
            surface_alt="#302a31",
            text="#fff4fb",
            muted="#d7bdce",
            border="#5e4d59",
            accent="#ff78c4",
            accent_hover="#ff9bd3",
            accent_text="#171418",
            selected="#493646",
        )
    return BacklogThemeTokens(
        mode="light",
        background="#e9e1e6",
        surface="#f5eef2",
        surface_alt="#dfd1d9",
        text="#21171e",
        muted="#66505e",
        border="#a98e9e",
        accent="#9e1f68",
        accent_hover="#c52f83",
        accent_text="#ffffff",
        selected="#dcb8cd",
    )
