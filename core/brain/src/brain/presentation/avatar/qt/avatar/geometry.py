# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Qt avatar and speech bubble placement, screen clamping, and window geometry events.

Calculates dialogue bubble positions to remain visible opposite the avatar,
constrains window coordinates within visible monitor boundaries,
resolves avatar-bubble overlaps by selecting the nearest available edge,
and computes screen-safe geometry for the attached reply composer.
"""

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
    """Calculate the global placement point for a speech bubble relative to the avatar.

    Positions the bubble window directly above or below the avatar so that the speech tail tip
    overlaps the avatar border by tail_tip_inset. If vertical screen space is insufficient,
    positions the bubble horizontally to the side of the avatar.

    Args:
        screen (QRect): Available screen geometry rectangle.
        avatar (QRect): Avatar window geometry rectangle.
        bubble (QSize): Target bubble dimensions including tail padding.
        tail_tip_inset (int): Distance in pixels that the tail tip inset overlaps into the avatar boundary.
        lane (str): Optional requested vertical lane preference ("above" or "below").

    Returns:
        QPoint: Clamped global top-left coordinates for placing the bubble window.
    """
    margin = 0

    # Horizontal alignment: align right edge if avatar is on the right half of the screen, else align left edge
    if avatar.center().x() >= screen.center().x():
        aligned_x = avatar.right() - bubble.width()
    else:
        aligned_x = avatar.left()

    # Candidate vertical position calculations:
    # Upper placement (above): bubble lower edge overlaps avatar top edge by tail_tip_inset
    # Lower placement (below): bubble upper edge overlaps avatar bottom edge by tail_tip_inset
    above_y = avatar.top() - bubble.height() + tail_tip_inset
    below_y = avatar.bottom() - tail_tip_inset

    # Viewport fit checks: verify whether candidate Y positions fit within top and bottom screen margins
    above_fits = above_y >= screen.top() + margin
    below_fits = below_y + bubble.height() <= screen.bottom() - margin

    # Placement preference: place above if avatar is located in the lower half of the screen
    prefer_above = avatar.center().y() >= screen.center().y()

    # Explicit lane selection: handle requested "above" lane
    if lane == "above" and above_fits:
        x, y = aligned_x, above_y

    # Explicit lane selection: handle requested "below" lane
    elif lane == "below" and below_fits:
        x, y = aligned_x, below_y

    # Natural preference branch: apply preference for upper placement
    elif prefer_above and above_fits:
        x, y = aligned_x, above_y

    # Natural preference branch: apply preference for lower placement
    elif not prefer_above and below_fits:
        x, y = aligned_x, below_y

    # Fallback selection: choose upper lane if space is available
    elif above_fits:
        x, y = aligned_x, above_y

    # Fallback selection: choose lower lane if space is available
    elif below_fits:
        x, y = aligned_x, below_y

    # Side fallback positioning: when top and bottom lanes fail, place bubble to the side centered vertically
    elif avatar.left() - screen.left() >= screen.right() - avatar.right():
        # Place bubble on left side centered vertically
        x, y = avatar.left() - bubble.width() + tail_tip_inset, avatar.center().y() - bubble.height() // 2
    else:
        # Place bubble on right side centered vertically
        x, y = avatar.right() - tail_tip_inset, avatar.center().y() - bubble.height() // 2

    # Clamping adjustment: ensure final coordinates stay within visible screen bounds
    return clamp_bubble_position(screen, bubble, QPoint(x, y), margin)


def clamp_bubble_position(screen: QRect, bubble: QSize, target: QPoint, margin: int = 18) -> QPoint:
    """Clamp requested bubble window coordinates within the visible screen area with padding.

    Calculates safe horizontal and vertical padding limits and constrains the target (X, Y)
    point so that neither edge of the bubble extends beyond the padded screen rectangle.

    Args:
        screen (QRect): Target screen geometry rectangle.
        bubble (QSize): Target bubble window dimensions.
        target (QPoint): Desired candidate top-left position coordinates.
        margin (int): Screen edge padding margin in pixels. Defaults to 18.

    Returns:
        QPoint: Clamped global top-left coordinates guaranteed to fit inside screen bounds.
    """
    # Padding limits: constrain padding to at most half of the available screen dimensions
    horizontal_margin = min(max(0, margin), max(0, (screen.width() - 1) // 2))
    vertical_margin = min(max(0, margin), max(0, (screen.height() - 1) // 2))

    # Safe inner rectangle boundaries: define padded screen area
    safe_left = screen.left() + horizontal_margin
    safe_top = screen.top() + vertical_margin
    safe_right = max(safe_left, screen.right() - horizontal_margin)
    safe_bottom = max(safe_top, screen.bottom() - vertical_margin)

    # Maximum top-left bounds: upper bounds for top-left X and Y to prevent overflow
    maximum_left = max(safe_left, safe_right - bubble.width() + 1)
    maximum_top = max(safe_top, safe_bottom - bubble.height() + 1)

    # Coordinate clamping: restrict X and Y between safe minimum and maximum bounds
    return QPoint(
        max(safe_left, min(target.x(), maximum_left)),
        max(safe_top, min(target.y(), maximum_top)),
    )


def bubble_vertical_lane(
    screen: QRect,
    avatar: QRect,
    bubble: QRect,
    preserve_position: bool,
    tail_tip_inset: int = 5,
    margin: int = 18,
) -> tuple[str, int | None]:
    """Classify the active vertical lane ("above" or "below") and compute maximum usable height.

    Evaluates whether the bubble sits above or below the avatar border and calculates
    the maximum vertical height available between the avatar anchor and the screen edge.

    Args:
        screen (QRect): Available screen geometry rectangle.
        avatar (QRect): Avatar window geometry rectangle.
        bubble (QRect): Current or requested bubble window rectangle.
        preserve_position (bool): Whether user-dragged manual positioning must be preserved.
        tail_tip_inset (int): Distance in pixels that the tail tip inset extends. Defaults to 5.
        margin (int): Required screen edge margin in pixels. Defaults to 18.

    Returns:
        tuple[str, int | None]: Tuple of (lane_name, max_usable_height_px) or ("", None).
    """

    # Upper lane classification: check if bubble is positioned above avatar top border
    if bubble.bottom() <= avatar.top() + tail_tip_inset:
        # Usable height calculation for upper lane: measure space from top margin to avatar top
        lane_bottom = bubble.bottom() if preserve_position else avatar.top() + tail_tip_inset
        return "above", max(1, lane_bottom - (screen.top() + margin))

    # Lower lane classification: check if bubble is positioned below avatar bottom border
    if bubble.top() >= avatar.bottom() - tail_tip_inset:
        # Usable height calculation for lower lane: measure space from avatar bottom to bottom margin
        lane_top = bubble.top() if preserve_position else avatar.bottom() - tail_tip_inset
        return "below", max(1, screen.bottom() - margin - lane_top + 1)

    return "", None


def avoid_avatar_overlap(viewport: QRect, avatar: QRect, bubble: QRect) -> QPoint:
    """Project an overlapping bubble to the nearest non-intersecting avatar edge.

    Evaluates four candidate projections (left, right, top, bottom) outside the avatar
    rectangle and selects the candidate that minimizes Manhattan distance to the original point.

    Args:
        viewport (QRect): Physical available screen viewport rectangle.
        avatar (QRect): Avatar window rectangle that must not be covered.
        bubble (QRect): Candidate bubble window rectangle.

    Returns:
        QPoint: Viewport-clamped top-left coordinates outside the avatar rectangle.
    """
    # Baseline viewport clamping: project candidate within screen bounds
    bounded = clamp_bubble_position(viewport, bubble.size(), bubble.topLeft(), margin=0)
    candidate = QRect(bounded, bubble.size())

    # Non-intersection verification: return baseline position if no overlap exists
    if not candidate.intersects(avatar):
        return bounded

    # Candidate placement generation: calculate adjacent points along avatar outer edges
    placements = (
        QPoint(avatar.left() - bubble.width(), candidate.top()),
        QPoint(avatar.right() + 1, candidate.top()),
        QPoint(candidate.left(), avatar.top() - bubble.height()),
        QPoint(candidate.left(), avatar.bottom() + 1),
    )
    valid: list[QPoint] = []

    # Placement validation: inspect each adjacent candidate for avatar overlap
    for placement in placements:
        projected = clamp_bubble_position(viewport, bubble.size(), placement, margin=0)

        # Intersection check: confirm candidate does not cover avatar window
        if not QRect(projected, bubble.size()).intersects(avatar):
            valid.append(projected)

    # Fallback handling: return baseline clamped point if no clear placement is found
    if not valid:
        return bounded

    # Distance minimization: select candidate point with minimum Manhattan offset
    return min(
        valid,
        key=lambda point: (point - bounded).manhattanLength(),
    )


def reply_composer_geometry(
    screen: QRect,
    bubble: QRect,
    above_avatar: bool,
    margin: int = 18,
    minimum_size: QSize | None = None,
    avatar: QRect | None = None,
    horizontal_margin: int | None = None,
) -> QRect:
    """Calculate screen-safe geometry for the attached reply composer facing the active bubble.

    Computes bounded width and height for the composer window based on screen margins,
    preferred vertical placement facing the bubble, and overlap avoidance relative to the avatar.

    Args:
        screen (QRect): Available physical screen geometry rectangle.
        bubble (QRect): Active speech bubble geometry rectangle.
        above_avatar (bool): Whether the speech bubble is placed above the avatar.
        margin (int): Screen edge margin in pixels. Defaults to 18.
        minimum_size (QSize | None): Minimum size constraints for the composer window.
        avatar (QRect | None): Optional avatar rectangle used for overlap checking.
        horizontal_margin (int | None): Optional horizontal override for exact bubble
            anchoring. The vertical margin always uses margin.

    Returns:
        QRect: Safe composer window geometry rectangle anchored to the bubble.
    """
    # Screen margin calculations: determine effective horizontal and vertical padding
    requested_horizontal_margin = (
        margin if horizontal_margin is None else horizontal_margin
    )
    horizontal_padding = min(
        max(0, requested_horizontal_margin),
        max(0, (screen.width() - 1) // 2),
    )
    vertical_margin = min(max(0, margin), max(0, (screen.height() - 1) // 2))

    # Inner safe area bounds: define usable screen dimensions
    safe_left = screen.left() + horizontal_padding
    safe_top = screen.top() + vertical_margin
    safe_right = max(safe_left, screen.right() - horizontal_padding)
    safe_bottom = max(safe_top, screen.bottom() - vertical_margin)
    safe_width = max(1, safe_right - safe_left + 1)
    safe_height = max(1, safe_bottom - safe_top + 1)

    # Dimension bounds: resolve requested and minimum window dimensions
    requested_width = max(1, bubble.width())
    requested_minimum_width = minimum_size.width() if minimum_size is not None else 1
    requested_minimum_height = (
        minimum_size.height() if minimum_size is not None else 180
    )
    width = min(safe_width, max(requested_width, requested_minimum_width, 1))
    minimum_height = min(safe_height, max(1, requested_minimum_height))
    left = max(safe_left, min(bubble.left(), safe_right - width + 1))

    # Avatar overlap check: handle lateral placement when bubble is level with avatar
    if avatar is not None:
        bubble_above = bubble.bottom() < avatar.top()
        bubble_below = bubble.top() > avatar.bottom()

        # Side alignment branch: bubble is positioned beside the avatar
        if not bubble_above and not bubble_below:
            height = min(safe_height, max(minimum_height, bubble.height()))
            top = max(safe_top, min(bubble.top(), safe_bottom - height + 1))
            candidate = QRect(left, top, width, height)

            # Overlap resolution: shift candidate if it intersects the avatar window
            if candidate.intersects(avatar):
                projected = avoid_avatar_overlap(screen, avatar, candidate)
                candidate.moveTo(projected)

            return candidate

        above_avatar = bubble_above

    # Lane ordering: prioritize primary vs secondary vertical lanes
    if above_avatar:
        preferred_lane = (safe_top, min(safe_bottom, bubble.bottom()))
        alternate_lane = (max(safe_top, bubble.top()), safe_bottom)
    else:
        preferred_lane = (max(safe_top, bubble.top()), safe_bottom)
        alternate_lane = (safe_top, min(safe_bottom, bubble.bottom()))

    # Lane evaluation: inspect candidate lanes for sufficient vertical space
    for lane_top, lane_bottom in (preferred_lane, alternate_lane):
        bounded_top = max(safe_top, min(lane_top, safe_bottom))
        bounded_bottom = max(bounded_top, min(lane_bottom, safe_bottom))
        height = bounded_bottom - bounded_top + 1

        # Capacity check: confirm lane height meets minimum height requirements
        if height >= minimum_height:
            return QRect(left, bounded_top, width, height)

    # Side fallback placement: position composer beside bubble when vertical space is narrow
    side_height = min(safe_height, max(minimum_height, min(bubble.height(), safe_height)))
    side_top = max(safe_top, min(bubble.top(), safe_bottom - side_height + 1))
    left_side = bubble.left() - width
    right_side = bubble.right() + 1
    preferred_side = left_side if bubble.center().x() >= screen.center().x() else right_side
    side_left = max(safe_left, min(preferred_side, safe_right - width + 1))

    return QRect(side_left, side_top, width, side_height)


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

        # Bubble initialization check: skip reset if bubble widget is not present
        if not hasattr(self, "bubble"):
            return

        self._reset_auxiliary_geometry()

    def _reset_auxiliary_geometry(self) -> None:
        """Reset bubble and composer geometry after an avatar relocation.

        Returns:
            None: Both auxiliary windows return to automatic geometry while their
            content and controller lifecycle remain untouched.
        """
        self._bubble_manual_position = None
        self._bubble_manual_bottom = None
        self._bubble_auto_lane = ""
        self.bubble.reset_geometry()
        self._reposition_bubble(force=True, reset_manual=True)

        reply_window = getattr(self, "reply_window", None)

        # Reply composer check: verify composer availability
        if reply_window is None:
            return

        screen = self.app.screenAt(self.frameGeometry().center()) or self.app.primaryScreen()

        # Active screen check: verify screen object presence
        if screen is None:
            return

        # Composer recalculation: recalculate composer bounds based on updated avatar/bubble geometry
        available = screen.availableGeometry()
        bubble_geometry = self.bubble.frameGeometry()
        above_avatar = bubble_geometry.center().y() < self.frameGeometry().center().y()
        minimum_size = reply_window.safe_minimum_size(available)
        composer_geometry = reply_composer_geometry(
            available,
            bubble_geometry,
            above_avatar,
            minimum_size=minimum_size,
            avatar=self.frameGeometry(),
        )
        reply_window.reset_geometry(composer_geometry)

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

        # Pointer synchronization: update pointer coordinates in controls overlay
        if visible:
            self.controls.sync_pointer(pointer)

        # Control layer elevation: bring controls widget to top z-order
        if self.controls.isVisible():
            self.controls.raise_()

    def mousePressEvent(self, event: object) -> None:  # noqa: N802 - Qt API
        """Start a left-button avatar drag.

        Args:
            event (object): Qt mouse-press event.

        Returns:
            None.
        """

        # Mouse press evaluation: record drag origin on left click
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

        # Drag tracking: update avatar position by global pointer offset
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

    def _constrain_bubble_drag(self) -> None:
        """Prevent a user drag from covering the avatar in real time.

        Returns:
            None: Only an actively dragged bubble may be projected to a free edge.
        """

        # Recursion guard: prevent nested execution of drag constraints
        if self._constraining_bubble_drag:
            return

        # Active drag check: verify bubble drag origin exists
        if self.bubble._drag_origin is None:
            return

        screen = self.app.screenAt(self.bubble.frameGeometry().center()) or self.app.primaryScreen()

        # Active screen check: verify screen object presence
        if screen is None:
            return

        target = avoid_avatar_overlap(
            screen.availableGeometry(),
            self.frameGeometry(),
            self.bubble.frameGeometry(),
        )

        # Position check: skip update if target position matches current position
        if target == self.bubble.pos():
            return

        self._constraining_bubble_drag = True

        # Execution safety: move bubble within protected try/finally block
        try:
            self.bubble.move(target)

        finally:
            self._constraining_bubble_drag = False

    def _retain_bubble_offset(self) -> None:
        """Store a clamped manual displacement relative to automatic placement.

        Returns:
            None.
        """
        screen = self.app.screenAt(self.frameGeometry().center()) or self.app.primaryScreen()

        # Active screen check: verify screen object presence
        if screen is None:
            return

        available = screen.availableGeometry()
        clamped = clamp_bubble_position(
            available,
            self.bubble.size(),
            self.bubble.pos(),
            margin=0,
        )
        self.bubble.move(clamped)

        lane, available_height = bubble_vertical_lane(
            available,
            self.frameGeometry(),
            self.bubble.frameGeometry(),
            preserve_position=True,
        )
        self.bubble.set_vertical_height_limit(bool(lane), available_height, fit_content=False)
        self._bubble_manual_position = QPoint(clamped)
        self._bubble_manual_bottom = self.bubble.frameGeometry().bottom()
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

        # Visibility check: skip repositioning if bubble is hidden and force is False
        if not force and (not hasattr(self, "bubble") or not self.bubble.isVisible()):
            return

        screen = self.app.screenAt(self.frameGeometry().center()) or self.app.primaryScreen()

        # Active screen check: verify screen object presence
        if screen is None:
            return

        available = screen.availableGeometry()
        avatar = self.frameGeometry()
        manual_bottom = self._bubble_manual_bottom

        # Manual position reset: clear stored manual coordinates if requested
        if reset_manual:
            self._bubble_manual_position = None
            self._bubble_manual_bottom = None

        manual_position = self._bubble_manual_position is not None

        # Position calculation: calculate target point based on manual or automatic mode
        if manual_position:
            target = clamp_bubble_position(
                available,
                self.bubble.size(),
                self._bubble_manual_position,
                margin=0,
            )
        else:
            self.bubble.set_vertical_height_limit(False)
            target = bubble_position(available, avatar, self.bubble.size())

        requested = QRect(target, self.bubble.size())
        lane, available_height = bubble_vertical_lane(available, avatar, requested, manual_position)
        self.bubble.set_vertical_height_limit(bool(lane), available_height)

        # Manual upper lane adjustment: adjust target Y to align bottom edge when in upper lane
        if manual_position and lane == "above" and manual_bottom is not None:
            target = QPoint(target.x(), manual_bottom - self.bubble.height() + 1)

        # Automatic placement recalculation: compute automatic bubble position
        elif not manual_position:
            target = bubble_position(available, avatar, self.bubble.size())

        target = clamp_bubble_position(
            available,
            self.bubble.size(),
            target,
            margin=0,
        )

        # Window movement: update bubble position if target differs from current position
        if self.bubble.pos() != target:
            self.bubble.move(target)

        # Manual state retention: update stored manual position
        if manual_position:
            self._bubble_manual_position = QPoint(target)

            # Manual bottom edge retention: update bottom edge if not in upper lane
            if lane != "above":
                self._bubble_manual_bottom = self.bubble.frameGeometry().bottom()
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

        # Visibility check: update tail target if bubble is visible
        if self.bubble.isVisible():
            self._update_tail()
