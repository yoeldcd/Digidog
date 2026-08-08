"""Resolution-independent value contracts for Qt backlog annotations."""
from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtCore import QPointF

ANNOTATION_PALETTE: dict[str, str] = {
    "Red": "#ff3b30",
    "Blue": "#168cff",
    "Green": "#22c55e",
    "Yellow": "#f6c945",
    "Magenta": "#ff4da6",
}
ANNOTATION_TOOLS = ("rectangle", "arrow", "path", "label")


@dataclass(slots=True)
class AnnotationMark:
    """One resolution-independent annotation over an immutable source image.

    Attributes:
        kind: Shape or annotation tool identifier.
        x: Normalized left coordinate in the source image.
        y: Normalized top coordinate in the source image.
        width: Normalized mark width.
        height: Normalized mark height.
        color: Stroke color serialized as a CSS-style value.
        label: Optional text attached to a label mark.
        points: Normalized freehand path points.
    """

    kind: str
    x: float
    y: float
    width: float
    height: float
    color: str
    label: str = ""
    points: tuple[QPointF, ...] = ()

    def copy(self) -> "AnnotationMark":
        """Return a detached value copy, including freehand points.

        Returns:
            AnnotationMark: Independent mark with copied freehand coordinates.
        """
        return replace(self, points=tuple(QPointF(point) for point in self.points))


@dataclass(slots=True)
class AnnotationGesture:
    """Transient pointer gesture retained by the annotation canvas.

    Attributes:
        mode: Active gesture mode such as draw, move, or resize.
        start: Normalized pointer coordinate where the gesture began.
        index: Selected mark index, or ``-1`` when no mark is selected.
        original: Snapshot of the selected mark before mutation.
    """

    mode: str
    start: QPointF
    index: int
    original: AnnotationMark | None = None
