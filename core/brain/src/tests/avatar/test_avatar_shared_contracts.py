# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Toolkit-neutral avatar presentation and interaction contracts."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from brain.presentation.avatar.communication.projection.daemon_status import DaemonStatusProjection
from brain.presentation.avatar.interactivity.history_controller import HistoryController
from brain.presentation.avatar.interactivity.interaction_controller import (
    AvatarControlIntent,
    InteractionController,
    ReactionIntent,
    ReplayTarget,
)
from brain.presentation.avatar.interactivity.presentation_state import (
    AvatarRuntimeState,
    ProjectedMessageState,
)
from brain.presentation.avatar.interactivity.quota_view_model import (
    QuotaThresholdTracker,
    QuotaViewModel,
    quota_decile,
)


def test_daemon_status_maps_transport_fields_and_active_ownership() -> None:
    """Daemon JSON becomes one typed presentation snapshot without widgets."""
    status = DaemonStatusProjection.from_mapping({
        "instanceId": "daemon-one",
        "state": "speaking",
        "activeSpeakId": "speak-four",
        "displayText": "Cuarto",
        "playbackActive": True,
        "progressivePlaybackActive": False,
        "processing": False,
        "queueDepth": 2,
        "historyCount": 4,
        "visualRemainingSeconds": 3.5,
    })

    presentation = status.presentation()

    assert presentation.runtime_state is AvatarRuntimeState.SPEAKING
    assert presentation.active_speak_id == "speak-four"
    assert presentation.owns_active_presentation is True
    assert presentation.speaking_animation_active is True
    assert presentation.processing_indicator_active is False
    assert (presentation.queue_depth, presentation.history_count) == (2, 4)


def test_daemon_status_keeps_rendering_separate_from_audible_playback() -> None:
    """Only declared render work owns processing chrome; preparing never implies it."""
    rendering = DaemonStatusProjection.from_mapping({
        "state": "preparing",
        "activeSpeakId": "rendering-one",
        "processing": True,
        "processingEmotion": "focused",
        "playbackActive": False,
    }).presentation()
    prepared = DaemonStatusProjection.from_mapping({
        "state": "preparing",
        "activeSpeakId": "prepared-one",
        "processing": False,
        "playbackActive": False,
    }).presentation()

    assert rendering.owns_active_presentation is False
    assert rendering.processing_indicator_active is True
    assert rendering.speaking_animation_active is False
    assert rendering.processing_emotion == "focused"
    assert prepared.owns_active_presentation is False
    assert prepared.processing_indicator_active is False


def test_status_projection_bounds_counters_and_recovers_unknown_enums() -> None:
    """Malformed transport values cannot leak negative counters or states."""
    status = DaemonStatusProjection.from_mapping({
        "state": "impossible",
        "muteMode": "impossible",
        "themeMode": "impossible",
        "queueDepth": -9,
        "historyCount": "bad",
        "visualRemainingSeconds": -4,
    })

    assert status.runtime_state is AvatarRuntimeState.AWAITING
    assert status.mute_mode == "off"
    assert status.theme_mode == "dark"
    assert (status.queue_depth, status.history_count, status.visual_remaining_seconds) == (0, 0, 0.0)


def test_primary_click_selects_terminal_stop_for_audible_or_muted_owner() -> None:
    """One click is STOP whenever a logical presentation owns the avatar."""
    for state in (AvatarRuntimeState.SPEAKING, AvatarRuntimeState.MUTED):
        presentation = ProjectedMessageState(
            runtime_state=state,
            active_speak_id="active",
            playback_active=state is AvatarRuntimeState.SPEAKING,
        )
        command = InteractionController.primary_click(
            presentation,
            ReplayTarget(speak_id="projected-history"),
        )
        assert command.intent is AvatarControlIntent.STOP
        assert command.endpoint == "/stop-current-message"
        assert dict(command.payload) == {}


def test_processing_phase_keeps_primary_control_in_play_mode() -> None:
    """Preparing audio uses its dedicated cancel control, not primary STOP."""
    presentation = ProjectedMessageState(
        runtime_state=AvatarRuntimeState.PREPARING,
        active_speak_id="preparing-one",
        playback_active=True,
        progressive_playback_active=True,
        processing=True,
    )
    command = InteractionController.primary_click(
        presentation,
        ReplayTarget(speak_id="preparing-one"),
    )

    assert presentation.owns_active_presentation is False
    assert command.intent is AvatarControlIntent.REPLAY
    assert command.endpoint == "/replay"


def test_primary_click_replays_exact_projected_identity_while_idle() -> None:
    """History replay never falls back to an older or implicit message."""
    command = InteractionController.primary_click(
        ProjectedMessageState(),
        ReplayTarget(speak_id="speak-four", browsing_history=True),
    )

    assert command.intent is AvatarControlIntent.REPLAY
    assert command.endpoint == "/replay"
    assert dict(command.payload) == {"speakId": "speak-four"}


def test_primary_click_narrates_active_manual_file_and_plays_fallback() -> None:
    """Manual file narration remains distinct from generic idle PLAY."""
    file_command = InteractionController.primary_click(
        ProjectedMessageState(),
        ReplayTarget(has_embedded_file=True, manual_speech=True),
    )
    fallback = InteractionController.primary_click(ProjectedMessageState())

    assert (file_command.intent, file_command.endpoint) == (
        AvatarControlIntent.PLAY,
        "/narrate-active-file",
    )
    assert (fallback.intent, fallback.endpoint) == (AvatarControlIntent.PLAY, "/replay")


def test_double_click_reacts_only_while_idle_and_clears_prior_queue() -> None:
    """Reaction is idle-only and carries the complete queue-cleaning contract."""
    reaction = ReactionIntent("Contacto", "happy")
    idle = InteractionController.double_click(ProjectedMessageState(), reaction)
    active = InteractionController.double_click(
        ProjectedMessageState(
            runtime_state=AvatarRuntimeState.SPEAKING,
            active_speak_id="active",
            playback_active=True,
        ),
        reaction,
    )

    assert idle.intent is AvatarControlIntent.REACTION
    assert idle.endpoint == "/speak"
    assert idle.payload["keepSpeaksOnly"] is True
    assert idle.payload["clearQueueBefore"] is True
    assert active.intent is AvatarControlIntent.STOP


def test_newest_first_history_uses_chronological_numbering_and_navigation() -> None:
    """Newest storage position zero is rendered as N/N, never 1/N."""
    history = HistoryController.from_mappings([
        {"id": "four", "displayText": "Cuarto"},
        {"id": "three", "displayText": "Tercero"},
        {"id": "two", "displayText": "Segundo"},
        {"id": "one", "displayText": "Primero"},
    ])

    newest = history.newest()
    assert newest is not None
    assert (newest.message.speak_id, newest.chronological_index, newest.total) == ("four", 4, 4)
    older = history.navigate("four", -1)
    assert older is not None
    assert (older.message.speak_id, older.chronological_index) == ("three", 3)
    oldest = history.select("one")
    assert oldest is not None
    assert (oldest.chronological_index, oldest.browsing_history) == (1, True)
    assert history.select("missing") is None
    newer = history.navigate("one", 1)
    assert newer is not None and newer.message.speak_id == "two"


def test_history_filters_non_display_records_without_losing_identity() -> None:
    """Batch/audio records without message text never become history pages."""
    history = HistoryController.from_mappings([
        {"id": "new", "text": "Nuevo", "audioName": "new.mp3"},
        {"id": "batch-only"},
    ])

    selected = history.newest()
    assert history.total == 1
    assert selected is not None
    assert selected.message.speak_id == "new"
    assert selected.message.audio_name == "new.mp3"


def test_quota_view_model_owns_bounds_animation_and_threshold_warnings() -> None:
    """Quota policy is shared independently from Qt and Tk drawing."""
    tracker = QuotaThresholdTracker()
    initial = QuotaViewModel.from_snapshot(SimpleNamespace(
        five_hour_percent=5,
        weekly_percent=89,
        five_hour_resets_at=0,
        weekly_resets_at=0,
    ))
    lowered = QuotaViewModel.from_snapshot(SimpleNamespace(
        five_hour_percent=11,
        weekly_percent=91,
        five_hour_resets_at=0,
        weekly_resets_at=0,
    ))

    assert initial.awaiting_animation == "happy"
    assert lowered.awaiting_animation == "sad"
    assert (lowered.five_hour_remaining, lowered.weekly_remaining) == (89, 9)
    assert lowered.five_hour_reset_label == "--:--"
    assert lowered.weekly_reset_label == "-- ---"
    assert tracker.consume(initial) == ()
    warnings = tracker.consume(lowered)
    assert "la cuota de cinco horas bajó a 89 por ciento restante" in warnings
    assert "la cuota semanal bajó a 9 por ciento restante" in warnings
    assert quota_decile(89) == 90


def test_shared_contract_modules_have_no_toolkit_import_direction() -> None:
    """Shared policy cannot depend on either concrete GUI backend."""
    avatar_root = Path(__file__).parents[2] / "brain" / "presentation" / "avatar"
    paths = [
        avatar_root / "interactivity" / "presentation_state.py",
        avatar_root / "interactivity" / "interaction_controller.py",
        avatar_root / "interactivity" / "history_controller.py",
        avatar_root / "interactivity" / "quota_view_model.py",
        avatar_root / "communication" / "projection" / "daemon_status.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "brain.presentation.avatar.qt" not in combined
    assert "brain.presentation.avatar.tk" not in combined
    assert "PySide" not in combined
    assert "tkinter" not in combined
