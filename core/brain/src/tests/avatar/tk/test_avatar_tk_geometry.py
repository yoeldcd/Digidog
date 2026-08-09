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


def test_default_geometry_is_upper_right() -> None:
    assert default_geometry(1920) == "270x360+1630+140"


def test_avatar_assets_use_state_names() -> None:
    assert avatar_asset("awaiting").name == "avatar_awaiting.gif"
    assert avatar_asset("speaking").name == "avatar_speaking.gif"
    assert avatar_asset("missing-emotion").name == "avatar_speaking.gif"
    assert avatar_asset("missing-quota-state", fallback_state="awaiting").name == "avatar_awaiting.gif"


def test_bubble_height_reserves_text_padding_and_bounded_tail() -> None:
    """Long messages must not lose body space to a height-proportional tail."""
    text_height = 420
    required = bubble_required_height(width=225, text_height=text_height)

    assert bubble_tail_height(225) == 18
    assert required >= text_height + 18 + 24 + 6


def test_dialogue_markdown_blocks_separates_metadata_from_dialogue() -> None:
    assert dialogue_markdown_blocks("ℹ️ [Render status slowly.] Processing complete, operator.") == [
        ("meta", "ℹ️ Render status slowly."),
        ("dialogue", "Processing complete, operator."),
    ]
    assert dialogue_markdown_blocks("Una respuesta directa") == [("dialogue", "Una respuesta directa")]


def test_detached_bubble_is_wide_and_appears_above_or_below_avatar() -> None:
    width = detached_bubble_width(screen_width=1920, avatar_width=270)
    x, y = detached_bubble_position(
        screen_size=(1920, 1080),
        avatar_bounds=(1630, 140, 270, 360),
        bubble_size=(width, 480),
    )

    assert BUBBLE_FONT[1] >= 12
    assert width == 810
    assert x == 1920 - 18 - width
    assert y == 140 + 360 + 18

    centered_x, above_y = detached_bubble_position(
        screen_size=(1920, 1080),
        avatar_bounds=(825, 700, 270, 360),
        bubble_size=(width, 480),
    )
    assert centered_x == 825 + (270 - width) // 2
    assert above_y == 700 - 18 - 480


def test_bubble_tail_tracks_avatar_from_an_angled_nearest_edge() -> None:
    assert bubble_tail_side((500, 100, 810, 260), (900, 400, 270, 360)) == "bottom"
    assert bubble_tail_side((500, 600, 810, 260), (900, 200, 270, 360)) == "top"
    assert bubble_tail_side((100, 300, 810, 260), (1200, 300, 270, 360)) == "right"

    body, points = bubble_tail_geometry("bottom", 810, 260, (730, 400))
    base_center = (points[0] + points[2]) // 2
    assert body[3] < points[5]
    assert base_center != points[4]


def test_bubble_drag_close_and_layout_are_independent_from_avatar() -> None:
    """Moving or resizing the avatar must not relocate its detached message."""
    import inspect

    init_source = inspect.getsource(AvatarWindow.__init__)
    drag_source = inspect.getsource(AvatarWindow._drag_move)
    resize_source = inspect.getsource(AvatarWindow._resize_move)
    hide_source = inspect.getsource(AvatarWindow._hide)
    dismiss_source = inspect.getsource(AvatarWindow._dismiss_bubble)
    assert 'self.bubble.bind("<ButtonPress-1>", self._bubble_pointer_press)' in init_source
    assert "self._position_bubble" not in drag_source
    assert "bubble" not in resize_source
    assert "bubble_root.withdraw" not in hide_source
    assert "self.bubble_root.withdraw()" in dismiss_source
    assert '"bubble-close-icon"' in inspect.getsource(AvatarWindow._draw_bubble)
    assert "_set_state" not in dismiss_source
    assert "player" not in dismiss_source


def test_canvas_close_and_nearest_corner_resize_contracts() -> None:
    import inspect

    draw_source = inspect.getsource(AvatarWindow._draw_bubble)
    pointer_source = inspect.getsource(AvatarWindow._bubble_pointer_motion)
    resize_source = inspect.getsource(AvatarWindow._bubble_resize_move)
    set_text_source = inspect.getsource(AvatarWindow._set_text)
    assert '"bubble-close-icon"' in draw_source
    assert 'tag_bind("bubble-close", "<ButtonPress-1>"' in draw_source
    assert "create_oval" in pointer_source
    assert "create_rectangle" not in pointer_source
    assert "BUBBLE_RESIZE_MIN_WIDTH" in resize_source
    assert "BUBBLE_RESIZE_MIN_HEIGHT" in resize_source
    assert "self.bubble_manual_size = (width, height)" in resize_source
    assert "if self.bubble_manual_size" in set_text_source

    class FakeBubble:
        def winfo_width(self) -> int:
            return 600

        def winfo_height(self) -> int:
            return 180

    window = object.__new__(AvatarWindow)
    window.bubble = FakeBubble()
    tail = bubble_tail_height(600)
    assert window._bubble_corner_at(tail + 2, tail + 2) == "nw"
    assert window._bubble_corner_at(600 - tail - 2, 180 - tail - 2) == "se"
    assert window._bubble_corner_at(300, 90) == ""
