# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Tk quota-ring geometry and raster painting."""

from __future__ import annotations

from PIL import ImageDraw, ImageFont

from brain.presentation.avatar.tk.controls.geometry import quota_ring_geometry


def quota_bar_color(percent: int) -> str:
    """Resolve a quota-ring color from consumed percentage.

    Args:
        percent (int): Consumed quota percentage.

    Returns:
        str: Hexadecimal semantic usage color.
    """
    if percent >= 75:
        return "#ff4f64"

    if percent >= 50:
        return "#ff982f"

    if percent >= 25:
        return "#f1d447"

    return "#36c978"


class TkQuotaPainterMixin:
    """Paint quota telemetry supplied by the shared quota view-model.

    Attributes:
        quotas (tuple[int, int] | None): Consumed quota percentages (five_hour, weekly).
        quota_visible (bool): Whether quota indicators should be drawn.
        quota_resets (tuple[str, str] | None): Reset display labels (five_hour, weekly).
    """

    def _draw_quota_indicators(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        """Draw five-hour and weekly progress rings beside playback.

        Args:
            draw (ImageDraw.ImageDraw): Pillow drawing context for the composed avatar frame.
            width (int): Current presentation width in pixels.
            height (int): Current presentation height in pixels.

        Returns:
            None.
        """
        if self.quotas is None or not self.quota_visible or width < 80:
            return

        left_center, right_center, ring_radius = quota_ring_geometry(width=width, height=height)
        ring_width = max(2, round(ring_radius * .20))

        try:
            value_font = ImageFont.truetype("segoeuib.ttf", max(8, round(ring_radius * .56)))
            label_font = ImageFont.truetype("segoeuib.ttf", max(10, round(ring_radius * .62)))
            reset_font = ImageFont.truetype("segoeui.ttf", max(7, round(ring_radius * .44)))
        except OSError:
            value_font = label_font = reset_font = ImageFont.load_default()

        for index, (label, percent) in enumerate(zip(("5h", "7d"), self.quotas)):
            remaining = 100 - percent
            center_x, center_y = left_center if index == 0 else right_center
            bounds = (center_x - ring_radius, center_y - ring_radius, center_x + ring_radius, center_y + ring_radius)

            draw.ellipse(bounds, fill="#101820", outline="#315078", width=ring_width)
            draw.arc(
                bounds, start=-90, end=-90 + round(360 * remaining / 100),
                fill=quota_bar_color(percent), width=ring_width,
            )

            value = f"{remaining}%"
            value_bounds = draw.textbbox((0, 0), value, font=value_font)
            draw.text(
                (
                    center_x - (value_bounds[2] - value_bounds[0]) / 2,
                    center_y - (value_bounds[3] - value_bounds[1]) / 2 - 3,
                ),
                value, font=value_font, fill="white",
            )

            label_bounds = draw.textbbox((0, 0), label, font=label_font)
            label_gap = max(5, round(ring_radius * .28))
            draw.text(
                (
                    center_x - (label_bounds[2] - label_bounds[0]) / 2,
                    center_y - ring_radius - (label_bounds[3] - label_bounds[1]) - label_gap,
                ),
                label, font=label_font, fill="#a9c8f7",
            )

            reset = self.quota_resets[index] if self.quota_resets else ""

            if reset:
                reset_bounds = draw.textbbox((0, 0), reset, font=reset_font)
                reset_x = center_x - (reset_bounds[2] - reset_bounds[0]) / 2
                reset_y = min(height - (reset_bounds[3] - reset_bounds[1]) - 1, center_y + ring_radius + 2)
                draw.text((reset_x, reset_y), reset, font=reset_font, fill="#a9c8f7")

