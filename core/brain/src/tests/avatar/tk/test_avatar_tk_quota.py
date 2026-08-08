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


def test_exhausted_quotas_select_tired_or_sad_awaiting_animation() -> None:
    """Ten percent remaining is sad weekly or tired for five hours."""
    assert AvatarWindow._quota_awaiting_animation(90, 50) == "tired"
    assert AvatarWindow._quota_awaiting_animation(50, 90) == "sad"
    assert AvatarWindow._quota_awaiting_animation(90, 90) == "sad"
    assert AvatarWindow._quota_awaiting_animation(89, 89) == "happy"


def test_quota_warnings_use_stable_ten_percent_units() -> None:
    assert AvatarWindow._quota_decile(96) == 100
    assert AvatarWindow._quota_decile(81) == 90
    assert AvatarWindow._quota_decile(80) == 80
    assert AvatarWindow._quota_decile(79) == 80
    assert AvatarWindow._quota_decile(69) == 70
    assert AvatarWindow._quota_decile(0) == 0


def test_quota_warning_trigger_keeps_exact_remaining_value_in_spoken_report() -> None:
    import inspect

    from brain.presentation.avatar.interactivity.quota_view_model import QuotaThresholdTracker, QuotaViewModel

    tracker = QuotaThresholdTracker()
    first = QuotaViewModel(10, 10, 90, 90, "", "", "happy")
    second = QuotaViewModel(21, 10, 79, 90, "", "", "happy")
    assert tracker.consume(first) == ()
    assert tracker.consume(second) == ("la cuota de cinco horas bajó a 79 por ciento restante",)


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
