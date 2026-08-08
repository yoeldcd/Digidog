# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

from unittest.mock import Mock

from brain.presentation.avatar.window.config import avatar_asset, default_geometry
from brain.presentation.avatar.tk.avatar import AnimatedGif, AvatarWindow
from brain.presentation.avatar.tk.bubble import (
    BUBBLE_FONT,
    bubble_required_height,
    bubble_tail_geometry,
    bubble_tail_height,
    bubble_tail_side,
    detached_bubble_position,
    detached_bubble_width,
    dialogue_markdown_blocks,
)
from brain.presentation.avatar.tk.controls import mute_button_geometry, playback_button_geometry
from brain.presentation.avatar.tk.quota import quota_bar_color, quota_ring_geometry
from brain.infrastructure.codex.quota_client import CodexQuotaClient, CodexQuotaSnapshot
from brain.presentation.avatar.window.native import NativeWindowPriority


def test_hd_gif_player_uses_bounded_framebuffer_budget() -> None:
    """The player source must retain a modest viewport-sized Tk cache."""
    import inspect

    source = inspect.getsource(AnimatedGif._draw)
    assert "24 * 1024 * 1024" in source
    assert 'frame = self.image.copy()' in source
    assert 'frame = frame.convert("RGBA")' in source
    assert source.index("frame.thumbnail") < source.index('frame = frame.convert("RGBA")')
    assert "if width <= 1 or height <= 1" in source


def test_quota_rings_share_playback_bottom_and_put_labels_above() -> None:
    """Keep quota rings aligned to playback while their labels sit above."""
    import inspect

    source = inspect.getsource(AnimatedGif._draw_quota_indicators)
    assert "center_y - ring_radius" in source
    assert "label_gap = max(5" in source
    left, right, radius = quota_ring_geometry(225, 300)
    assert left[1] + radius == right[1] + radius < 294
    assert left[0] < 225 // 2 < right[0]
    _, play_radius = playback_button_geometry(225, 300)
    former_play_radius = round(225 * .10)
    assert radius == round(former_play_radius * .78)
    assert right[0] - 225 // 2 == play_radius + radius + max(4, round(225 * .025))


def test_playback_control_is_thirty_percent_larger_and_uses_one_hitbox() -> None:
    center, radius = playback_button_geometry(270, 360)

    assert center == (135, 360 - radius - max(6, round(360 * .02)))
    assert radius == round(270 * .13)
    assert radius == round(round(270 * .10) * 1.30)
    draw_source = __import__("inspect").getsource(AnimatedGif._draw)
    click_source = __import__("inspect").getsource(AvatarWindow._label_click)
    assert "playback_button_geometry" in draw_source
    assert "playback_button_geometry" in click_source


def test_mute_control_owns_a_proportional_lower_left_hitbox() -> None:
    center, radius = mute_button_geometry(270, 360)

    assert center[0] == radius + max(5, round(270 * .025))
    assert center[1] == 360 - radius - max(5, round(270 * .025))
    assert radius == round(270 * .048)
    assert 10 <= radius <= 16
    draw_source = __import__("inspect").getsource(AnimatedGif._draw_mute_button)
    assert 'outline="#3b8cff"' in draw_source
    assert "fill=(18, 59, 120, 150)" in draw_source
    assert "icon_center_x" in draw_source
    assert "if self.muted" in draw_source


def test_quota_refresh_blinks_and_restores_visibility() -> None:
    """Refreshing must blink both rings and leave them visible afterward."""
    import inspect

    source = inspect.getsource(AnimatedGif.set_quota_refreshing)
    toggle_source = inspect.getsource(AnimatedGif._toggle_quota_blink)
    assert "self.quota_visible = True" in source
    assert "self.quota_visible = not self.quota_visible" in toggle_source
    assert "after(320" in toggle_source


def test_controls_can_hide_without_removing_avatar_framebuffer() -> None:
    """Hover visibility suppresses controls without suppressing the avatar."""
    import inspect

    source = inspect.getsource(AnimatedGif._draw)
    assert "if self.avatar_visible:" in source
    assert "if self.controls_visible:" in source
    setter = inspect.getsource(AnimatedGif.set_controls_visible)
    assert "self.framebuffer.clear()" in setter


def test_global_pointer_hover_hides_all_controls_and_close_is_removed() -> None:
    import inspect

    poll_source = inspect.getsource(AvatarWindow._poll_control_hover)
    visibility_source = inspect.getsource(AvatarWindow._set_controls_visible)
    build_source = inspect.getsource(AvatarWindow._build_controls)
    assert "winfo_pointerxy" in poll_source
    assert "self.player.set_controls_visible(visible)" in visibility_source
    assert "self._layout_controls()" in visibility_source
    assert "self.close" not in build_source
    assert not hasattr(AvatarWindow, "_toggle_avatar_layout")
