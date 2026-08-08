# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Qt avatar and bubble placement plus window geometry events."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QCursor


def bubble_position(
    screen: QRect,
    avatar: QRect,
    bubble: QSize,
    tail_tip_inset: int = 5,
    lane: str = "",
) -> QPoint:
    """Place the bubble body opposite the avatar and touch it with the tail tip.

    Args:
        screen (QRect): Available screen geometry.
        avatar (QRect): Avatar window geometry.
        bubble (QSize): Bubble dimensions including transparent tail insets.
        tail_tip_inset (int): Tail-tip distance from the bubble window edge.
        lane (str): Optional fixed vertical lane (``above`` or ``below``).

    Returns:
        QPoint: Bounded global bubble position.
    """
    margin = 18
    if avatar.center().x() >= screen.center().x():
        aligned_x = avatar.right() - bubble.width()
    else:
        aligned_x = avatar.left()
    above_y = avatar.top() - bubble.height() + tail_tip_inset
    below_y = avatar.bottom() - tail_tip_inset
    above_fits = above_y >= screen.top() + margin
    below_fits = below_y + bubble.height() <= screen.bottom() - margin
    prefer_above = avatar.center().y() >= screen.center().y()
    if lane == "above" and above_fits:
        x, y = aligned_x, above_y
    elif lane == "below" and below_fits:
        x, y = aligned_x, below_y
    elif prefer_above and above_fits:
        x, y = aligned_x, above_y
    elif not prefer_above and below_fits:
        x, y = aligned_x, below_y
    elif above_fits:
        x, y = aligned_x, above_y
    elif below_fits:
        x, y = aligned_x, below_y
    elif avatar.left() - screen.left() >= screen.right() - avatar.right():
        x, y = avatar.left() - bubble.width() + tail_tip_inset, avatar.center().y() - bubble.height() // 2
    else:
        x, y = avatar.right() - tail_tip_inset, avatar.center().y() - bubble.height() // 2
    return QPoint(
        max(screen.left() + margin, min(x, screen.right() - bubble.width() - margin)),
        max(screen.top() + margin, min(y, screen.bottom() - bubble.height() - margin)),
    )

def clamp_bubble_position(screen: QRect, bubble: QSize, target: QPoint, margin: int = 18) -> QPoint:
    """Clamp a requested bubble position to the visible screen rectangle.

    Args:
        screen (QRect): Target screen geometry rectangle.
        bubble (QSize): Target bubble dimensions.
        target (QPoint): Desired candidate position point.
        margin (int): Screen edge padding margin. Defaults to 18.

    Returns:
        QPoint: Clamped position within screen bounds.
    """
    return QPoint(
        max(screen.left() + margin, min(target.x(), screen.right() - bubble.width() - margin)),
        max(screen.top() + margin, min(target.y(), screen.bottom() - bubble.height() - margin)),
    )

def bubble_vertical_lane(
    screen: QRect,
    avatar: QRect,
    bubble: QRect,
    preserve_position: bool,
    tail_tip_inset: int = 5,
    margin: int = 18,
) -> tuple[str, int | None]:
    """Resolve a detached vertical lane and its usable height.

    Args:
        screen (QRect): Available screen geometry.
        avatar (QRect): Avatar window geometry.
        bubble (QRect): Current or requested bubble geometry.
        preserve_position (bool): Whether the user-selected bubble origin must remain fixed.
        tail_tip_inset (int): Tail-tip distance from the bubble window edge.
        margin (int): Required separation from the screen edge.

    Returns:
        tuple[str, int | None]: Lane name and maximum usable height, or an empty lane.
    """
    if bubble.bottom() <= avatar.top() + tail_tip_inset:
        # A manually placed bubble above the avatar grows upward from its own
        # lower edge. Its free space is therefore above, not the small gap to
        # the avatar below it.
        lane_bottom = bubble.bottom() if preserve_position else avatar.top() + tail_tip_inset
        return "above", max(1, lane_bottom - (screen.top() + margin))
    if bubble.top() >= avatar.bottom() - tail_tip_inset:
        lane_top = bubble.top() if preserve_position else avatar.bottom() - tail_tip_inset
        return "below", max(1, screen.bottom() - margin - lane_top + 1)
    return "", None

def reply_composer_geometry(screen: QRect, bubble: QRect, above_avatar: bool, margin: int = 18) -> QRect:
    """Calculate composer geometry facing the active bubble.

    Args:
        screen (QRect): Available screen geometry.
        bubble (QRect): Current bubble geometry.
        above_avatar (bool): Whether the bubble sits above the avatar.
        margin (int): Screen margin in pixels.

    Returns:
        QRect: Composer bounds anchored to the bubble side.
    """
    left = max(screen.left() + margin, min(bubble.left(), screen.right() - margin - bubble.width()))
    if above_avatar:
        top = screen.top() + margin
        bottom = min(screen.bottom() - margin, bubble.bottom())
    else:
        top = max(screen.top() + margin, bubble.top())
        bottom = screen.bottom() - margin
    return QRect(left, top, bubble.width(), max(180, bottom - top + 1))


class QtWindowGeometryMixin:
    """Mixin managing avatar window geometry events, drags, and message bubble positioning."""

    def resizeEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Resize avatar layers and reposition a visible message bubble.

        Args:
            event (object): Qt resize event.

        Returns:
            None.
        """
        super().resizeEvent(event)
        self.avatar.setGeometry(self.rect())
        self.controls.setGeometry(self.rect())
        self.controls.raise_()
        self._render_movie_frame()
        self._reposition_bubble()

    def moveEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Keep a visible dialogue attached after every native avatar move.

        Args:
            event (object): Qt move event.

        Returns:
            None.
        """
        super().moveEvent(event)
        self._bubble_manual_position = None
        self._reposition_bubble()

    def enterEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Reveal and raise controls when the pointer enters the avatar.

        Args:
            event (object): Qt enter event.

        Returns:
            None.
        """
        self.controls.set_expanded(True)
        self.controls.raise_()
        super().enterEvent(event)

    def leaveEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Delegate pointer-leave handling to the base Qt widget.

        Args:
            event (object): Qt leave event.

        Returns:
            None.
        """
        self.controls.set_expanded(False)
        super().leaveEvent(event)

    def _sync_hover(self) -> None:
        """Synchronize control overlay visibility and pointer position.

        Returns:
            None.
        """
        pointer = QCursor.pos()
        local_pointer = self.mapFromGlobal(pointer)
        visible = self.rect().contains(local_pointer)
        self.controls.set_expanded(visible)

        if visible:
            self.controls.sync_pointer(pointer)
        if self.controls.isVisible():
            self.controls.raise_()

    def mousePressEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Start a left-button avatar drag.

        Args:
            event (object): Qt mouse-press event.

        Returns:
            None.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pointer = event.globalPosition().toPoint()
            self._drag_origin = self.pos()
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Move the avatar and its tail target while dragging.

        Args:
            event (object): Qt mouse-move event.

        Returns:
            None.
        """
        if self._drag_pointer is not None and self._drag_origin is not None:
            self.move(self._drag_origin + event.globalPosition().toPoint() - self._drag_pointer)
            self._update_tail()
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Clear the current avatar drag state.

        Args:
            event (object): Qt mouse-release event.

        Returns:
            None.
        """
        self._drag_pointer = None
        self._drag_origin = None
        super().mouseReleaseEvent(event)

    def _update_tail(self) -> None:
        """Update bubble tail target to point at the avatar center.

        Returns:
            None.
        """
        self.bubble.set_tail_target(self.mapToGlobal(self.rect().center()))

    def _retain_bubble_offset(self) -> None:
        """Store a clamped manual displacement relative to automatic placement.

        Returns:
            None.
        """
        screen = self.app.screenAt(self.frameGeometry().center()) or self.app.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        clamped = clamp_bubble_position(available, self.bubble.size(), self.bubble.pos())
        self.bubble.move(clamped)

        lane, available_height = bubble_vertical_lane(
            available,
            self.frameGeometry(),
            self.bubble.frameGeometry(),
            preserve_position=True,
        )
        self.bubble.set_vertical_height_limit(bool(lane), available_height, fit_content=False)
        self._bubble_manual_position = QPoint(clamped)
        self._bubble_auto_lane = ""
        self._update_tail()

    def _reposition_bubble(self, force: bool = False, reset_manual: bool = False) -> None:
        """Apply manual placement or keep automatic geometry justified to the avatar.

        Args:
            force (bool): Whether to force repositioning even if bubble is hidden.
            reset_manual (bool): Whether to clear manual position displacement.

        Returns:
            None.
        """
        if not force and (not hasattr(self, "bubble") or not self.bubble.isVisible()):
            return

        screen = self.app.screenAt(self.frameGeometry().center()) or self.app.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        avatar = self.frameGeometry()
        manual_bottom = self.bubble.frameGeometry().bottom()

        if reset_manual:
            self._bubble_manual_position = None

        manual_position = self._bubble_manual_position is not None
        if manual_position:
            target = clamp_bubble_position(available, self.bubble.size(), self._bubble_manual_position)
        else:
            self.bubble.set_vertical_height_limit(False)
            target = bubble_position(available, avatar, self.bubble.size())

        requested = QRect(target, self.bubble.size())
        lane, available_height = bubble_vertical_lane(available, avatar, requested, manual_position)
        self.bubble.set_vertical_height_limit(bool(lane), available_height)

        if manual_position and lane == "above":
            target = QPoint(target.x(), manual_bottom - self.bubble.height() + 1)
        elif not manual_position:
            target = bubble_position(available, avatar, self.bubble.size())

        target = clamp_bubble_position(available, self.bubble.size(), target)
        if self.bubble.pos() != target:
            self.bubble.move(target)

        if manual_position:
            self._bubble_manual_position = QPoint(target)
            self._bubble_auto_lane = ""
        else:
            self._bubble_auto_lane = lane

        self.bubble.set_vertical_placement(lane == "above")
        self._update_tail()

    def _refresh_tail(self) -> None:
        """Refresh the bubble tail if visible.

        Returns:
            None.
        """
        if self.bubble.isVisible():
            self._update_tail()

