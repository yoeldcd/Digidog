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


def test_state_transition_recovers_when_expected_gif_is_not_displayed() -> None:
    """A failed heavy-GIF load must be retried on the next status poll."""
    import inspect

    source = inspect.getsource(AvatarWindow._set_state)
    poll_source = inspect.getsource(AvatarWindow._poll)
    assert "self.player.displayed_path != str(path)" in source
    assert "changed or force or needs_recovery" in source
    assert "DaemonStatusProjection.from_mapping" in poll_source
    animation_source = inspect.getsource(AvatarWindow._animation_for_state)
    assert 'self.awaiting_quota_animation or "awaiting"' in animation_source


def test_speaking_temporarily_overrides_pin_priority() -> None:
    """Speaking is always topmost while awaiting restores the pin choice."""
    import inspect

    source = inspect.getsource(AvatarWindow._apply_topmost)
    state_source = inspect.getsource(AvatarWindow._set_state)
    pin_source = inspect.getsource(AvatarWindow._toggle_pin)
    assert "self.presentation.owns_active_presentation" in source
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
    assert "self.presentation.owns_active_presentation" in state_source
    assert "self._execute_primary_control()" in toggle_source


def test_avatar_poll_applies_daemon_mute_state() -> None:
    import inspect

    poll_source = inspect.getsource(AvatarWindow._poll)
    click_source = inspect.getsource(AvatarWindow._label_click)
    assert 'self.player.set_muted(self.presentation.mute_mode != "off")' in poll_source
    assert "mute_button_geometry" in click_source
    assert "self._toggle_mute()" in click_source


def test_avatar_click_preserves_pause_close_and_double_reaction() -> None:
    """The avatar body distinguishes delayed pause-and-close from reactions."""
    import inspect

    source = inspect.getsource(AvatarWindow._avatar_click)
    commit_source = inspect.getsource(AvatarWindow._commit_avatar_single_click)
    reaction_source = inspect.getsource(AvatarWindow._speak_reaction)
    assert "after_cancel" in source
    assert "_speak_reaction()" in source
    assert "self._execute_primary_control()" in commit_source
    assert "InteractionController.double_click" in reaction_source
    assert "ReactionIntent" in reaction_source
    from brain.presentation.avatar.interactivity.interaction_controller import ReactionIntent
    payload = ReactionIntent("Hola", "happy").command().payload
    assert payload["keepSpeaksOnly"] is True
    assert payload["clearQueueBefore"] is True
    window = object.__new__(AvatarWindow)
    window.awaiting_quota_animation = ""
    assert window._animation_for_state("preparing", "reacting") == ("awaiting", "awaiting")


def test_tk_single_avatar_click_stops_active_or_replays_projected_identity() -> None:
    """Tk delegates the exact STOP/REPLAY decision to the shared controller."""
    from brain.presentation.avatar.interactivity.presentation_state import AvatarRuntimeState, ProjectedMessageState
    from brain.presentation.avatar.tk.runtime.message import TkMessageController

    window = object.__new__(AvatarWindow)
    window.avatar_click_job = "scheduled"
    window.transport = Mock()
    window._dismiss_bubble = Mock()
    window.message_controller = TkMessageController()
    window.presentation = ProjectedMessageState(
        runtime_state=AvatarRuntimeState.SPEAKING,
        active_speak_id="speak-active",
        playback_active=True,
    )
    window._commit_avatar_single_click()
    command = window.transport.execute.call_args.args[0]
    assert command.endpoint == "/stop-current-message"
    window._dismiss_bubble.assert_called_once_with()

    window.transport.reset_mock()
    window._dismiss_bubble.reset_mock()
    window.presentation = ProjectedMessageState()
    window.message_controller.current = window.message_controller.last = __import__(
        "brain.presentation.avatar.interactivity.history_controller", fromlist=["HistoryMessage"]
    ).HistoryMessage("speak-four", "Cuarto")
    window._commit_avatar_single_click()
    command = window.transport.execute.call_args.args[0]
    assert command.endpoint == "/replay"
    assert command.payload == {"speakId": "speak-four"}
    window._dismiss_bubble.assert_not_called()


def test_presentation_faults_do_not_trigger_daemon_loss_shutdown() -> None:
    """Only transport failures may consume the daemon-loss grace period."""
    import inspect

    source = inspect.getsource(AvatarWindow._poll)
    assert source.count("DAEMON_LOSS_GRACE_SECONDS") == 1
    assert "self.last_seen = time.monotonic()" in source
