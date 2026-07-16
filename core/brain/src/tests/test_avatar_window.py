# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

from brain.presentation.avatar.window.config import avatar_asset, default_geometry
from brain.presentation.avatar.tk.window import (
    BUBBLE_FONT,
    AvatarWindow,
    bubble_required_height,
    bubble_tail_geometry,
    bubble_tail_height,
    bubble_tail_side,
    detached_bubble_position,
    detached_bubble_width,
    dialogue_markdown_blocks,
)
from brain.presentation.avatar.tk.animated_gif import (
    AnimatedGif,
    mute_button_geometry,
    playback_button_geometry,
    quota_bar_color,
    quota_ring_geometry,
)
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


def test_dialogue_markdown_blocks_separates_narrative_from_dialogue() -> None:
    assert dialogue_markdown_blocks("😴 [Meneo la colita lentamente.] Buenas noches, papi.") == [
        ("meta", "😴 Meneo la colita lentamente."),
        ("dialogue", "Buenas noches, papi."),
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


def test_hd_gif_player_uses_bounded_framebuffer_budget() -> None:
    """The player source must retain a modest viewport-sized Tk cache."""
    import inspect

    source = inspect.getsource(AnimatedGif._draw)
    assert "24 * 1024 * 1024" in source
    assert 'frame = self.image.copy()' in source
    assert 'frame = frame.convert("RGBA")' in source
    assert source.index("frame.thumbnail") < source.index('frame = frame.convert("RGBA")')
    assert "if width <= 1 or height <= 1" in source


def test_codex_quota_payload_maps_five_hour_and_weekly_windows() -> None:
    snapshot = CodexQuotaClient._parse_snapshot({
        "rateLimits": {
            "primary": {"usedPercent": 21, "resetsAt": 1000},
            "secondary": {"usedPercent": 22, "resetsAt": 2000},
        }
    })

    assert snapshot.five_hour_percent == 21
    assert snapshot.weekly_percent == 22
    assert quota_bar_color(24) == "#36c978"
    assert quota_bar_color(25) == "#f1d447"
    assert quota_bar_color(50) == "#ff982f"
    assert quota_bar_color(75) == "#ff4f64"
    assert 100 - snapshot.five_hour_percent == 79
    assert 100 - snapshot.weekly_percent == 78


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


def test_exhausted_quotas_select_tired_or_sad_awaiting_animation() -> None:
    """Ten percent remaining is sad weekly or tired for five hours."""
    assert AvatarWindow._quota_awaiting_animation(90, 50) == "tired"
    assert AvatarWindow._quota_awaiting_animation(50, 90) == "sad"
    assert AvatarWindow._quota_awaiting_animation(90, 90) == "sad"
    assert AvatarWindow._quota_awaiting_animation(89, 89) == ""


def test_quota_warnings_use_stable_ten_percent_units() -> None:
    assert AvatarWindow._quota_decile(96) == 100
    assert AvatarWindow._quota_decile(81) == 90
    assert AvatarWindow._quota_decile(80) == 80
    assert AvatarWindow._quota_decile(79) == 80
    assert AvatarWindow._quota_decile(69) == 70
    assert AvatarWindow._quota_decile(0) == 0


def test_quota_warning_trigger_keeps_exact_remaining_value_in_spoken_report() -> None:
    import inspect

    source = inspect.getsource(AvatarWindow._consume_quota_result)
    assert 'current_decile < announced[index]' in source
    assert 'bajó a {remaining[index]} por ciento restante' in source


def test_weekly_only_quota_payload_uses_explicit_five_hour_fallback() -> None:
    snapshot = CodexQuotaClient._parse_snapshot({
        "rateLimits": {"secondary": {"usedPercent": 28, "resetsAt": 2_000_000_000}}
    })

    assert snapshot.five_hour_percent == 0
    assert snapshot.five_hour_resets_at == 0
    assert snapshot.weekly_percent == 28
    assert snapshot.weekly_resets_at == 2_000_000_000
    assert AvatarWindow._quota_reset_labels(snapshot)[0] == "--:--"


def test_duration_schema_recognizes_weekly_window_in_primary_slot() -> None:
    snapshot = CodexQuotaClient._parse_snapshot({
        "rateLimits": {
            "primary": {
                "usedPercent": 1,
                "windowDurationMins": 10080,
                "resetsAt": 2_000_000_000,
            },
            "secondary": None,
        }
    })

    assert snapshot.five_hour_percent == 0
    assert snapshot.five_hour_resets_at == 0
    assert snapshot.weekly_percent == 1
    assert snapshot.weekly_resets_at == 2_000_000_000


def test_incomplete_weekly_quota_payload_is_rejected() -> None:
    try:
        CodexQuotaClient._parse_snapshot({"rateLimits": {"primary": {"usedPercent": 4}}})
    except ValueError as error:
        assert "weekly" in str(error)
    else:
        raise AssertionError("Incomplete quota payload unexpectedly became a snapshot")


def test_quota_reset_labels_use_local_time_and_deterministic_gregorian_month() -> None:
    from datetime import datetime

    five_hour = int(datetime(2026, 7, 11, 23, 45).astimezone().timestamp())
    weekly = int(datetime(2026, 7, 14, 9, 0).astimezone().timestamp())
    snapshot = CodexQuotaSnapshot(10, 20, five_hour, weekly)
    assert AvatarWindow._quota_reset_labels(snapshot) == ("23:45", "14 JUL")


def test_state_transition_recovers_when_expected_gif_is_not_displayed() -> None:
    """A failed heavy-GIF load must be retried on the next status poll."""
    import inspect

    source = inspect.getsource(AvatarWindow._set_state)
    poll_source = inspect.getsource(AvatarWindow._poll)
    assert "self.player.displayed_path != str(path)" in source
    assert "changed or force or needs_recovery" in source
    assert '\"happy\" if state == \"speaking\" else \"\"' in poll_source
    animation_source = inspect.getsource(AvatarWindow._animation_for_state)
    assert 'self.awaiting_quota_animation or "awaiting"' in animation_source


def test_speaking_temporarily_overrides_pin_priority() -> None:
    """Speaking is always topmost while awaiting restores the pin choice."""
    import inspect

    source = inspect.getsource(AvatarWindow._apply_topmost)
    state_source = inspect.getsource(AvatarWindow._set_state)
    pin_source = inspect.getsource(AvatarWindow._toggle_pin)
    assert 'self.state in {"preparing", "speaking"}' in source
    assert "self.is_pinned or playback_active" in source
    assert "self._apply_topmost()" in state_source
    assert "self._apply_topmost()" in pin_source
    native_source = inspect.getsource(NativeWindowPriority.apply)
    assert "SetWindowPos" in native_source
    assert "SW_SHOWNOACTIVATE" in native_source
    assert "SWP_NOACTIVATE" in native_source


def test_thinking_uses_awaiting_animation_until_playback_starts() -> None:
    """Thinking changes only the bubble; speaking owns the speaking GIF."""
    window = object.__new__(AvatarWindow)
    window.awaiting_quota_animation = ""
    assert window._animation_for_state("thinking", "thinking") == ("awaiting", "awaiting")
    assert window._animation_for_state("muted", "happy") == ("awaiting", "awaiting")
    assert window._animation_for_state("muted_replay", "happy") == ("awaiting", "awaiting")
    assert window._animation_for_state("speaking", "happy") == ("happy", "speaking")


def test_muted_visual_replay_owns_pause_icon_and_pause_endpoint() -> None:
    import inspect

    state_source = inspect.getsource(AvatarWindow._set_state)
    toggle_source = inspect.getsource(AvatarWindow._toggle_playback)
    assert 'state in {"muted_replay", "speaking"}' in state_source
    assert 'self.state in {"muted_replay", "preparing", "speaking"}' in toggle_source


def test_avatar_poll_applies_daemon_mute_state() -> None:
    import inspect

    poll_source = inspect.getsource(AvatarWindow._poll)
    click_source = inspect.getsource(AvatarWindow._label_click)
    assert 'self.player.set_muted(bool(payload.get("muted", False)))' in poll_source
    assert "mute_button_geometry" in click_source
    assert "self._toggle_mute()" in click_source


def test_second_click_queues_reacting_speech_with_one_second_prelude() -> None:
    """Only the second consecutive click requests the reacting speaking mode."""
    import inspect

    source = inspect.getsource(AvatarWindow._avatar_click)
    assert "self.click_count >= 2" in source
    assert '"emotion": "reacting"' in source
    assert '"preludeSeconds": 1' in source
    assert 'avatar_asset("reacting")' not in source
    window = object.__new__(AvatarWindow)
    window.awaiting_quota_animation = ""
    assert window._animation_for_state("preparing", "reacting") == ("reacting", "speaking")


def test_presentation_faults_do_not_trigger_daemon_loss_shutdown() -> None:
    """Only transport failures may consume the daemon-loss grace period."""
    import inspect

    source = inspect.getsource(AvatarWindow._poll)
    assert source.count("DAEMON_LOSS_GRACE_SECONDS") == 1
    assert "self.last_seen=time.monotonic()" in source
