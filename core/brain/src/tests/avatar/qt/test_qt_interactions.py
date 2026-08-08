# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Qt avatar interaction and transport contract tests."""
import json
import os
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPixmap
from PySide6.QtTest import QTest

from brain.presentation.avatar.qt.controls.geometry import backlog_geometry, capture_geometry
from brain.presentation.avatar.qt.backlog.application.controller import BacklogController
from brain.presentation.avatar.qt.backlog.contracts.models import ProjectView, TaskView
from brain.presentation.avatar.qt.backlog.presentation.window import BacklogWindow

from brain.presentation.avatar.window.backend import requested_avatar_backend, resolve_avatar_window_class
from brain.presentation.avatar.interactivity.markdown_document import (
    avatar_markdown_source,
    expand_avatar_images,
    normalize_avatar_markdown,
    render_embedded_file_blocks,
)
from brain.presentation.avatar.interactivity.reactions import AvatarReactionDTO, ReactionPhraseBag
from brain.presentation.avatar.qt.bubble import (
    QtMarkdownBubble,
    normalized_image_size,
    semantic_token_ranges,
    table_column_percentages,
)
from brain.presentation.avatar.qt.runtime import (
    QtAvatarWindow,
    bubble_position,
    bubble_vertical_lane,
    fit_avatar_frame,
    quota_reset_label,
    reply_composer_geometry,
)
from brain.presentation.avatar.tk.avatar.window import AvatarWindow


def test_configured_double_click_reaction_uses_message_and_animation() -> None:
    """The double-click request forwards one complete configured reaction."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.reaction_bag = ReactionPhraseBag(reactions=[
        AvatarReactionDTO(message="Sent├¡ tus dos clics", animation="animation_1.gif"),
    ])

    with patch("brain.presentation.avatar.qt.runtime.backend_adapter.urlopen") as send:
        window._speak_reaction()

    request = send.call_args.args[0]
    payload = json.loads(request.data)
    assert payload["text"] == "Sent├¡ tus dos clics"
    assert payload["emotion"] == "animation_1.gif"
    assert payload["keepSpeaksOnly"] is True
    assert payload["clearQueueBefore"] is True
    window.close()

def test_ignore_quota_state_keeps_awaiting_animation_neutral() -> None:
    """Quota meters still update while quota-driven avatar emotion stays disabled."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.ignore_quota_state = True
    window.awaiting_quota_animation = "sad"
    window.quota_results.put(SimpleNamespace(
        five_hour_percent=95,
        weekly_percent=95,
        five_hour_resets_at=0,
        weekly_resets_at=0,
    ))

    window._consume_quota_result()

    assert window.awaiting_quota_animation == ""
    window.close()

def test_backend_defaults_to_qt_and_keeps_explicit_tk_fallback() -> None:
    assert requested_avatar_backend({}) == "qt"
    assert resolve_avatar_window_class({}) is QtAvatarWindow
    assert resolve_avatar_window_class({"BRAIN_AVATAR_UI": "tk"}) is AvatarWindow
    assert requested_avatar_backend({"BRAIN_AVATAR_UI": "QT"}) == "qt"
    assert requested_avatar_backend({"BRAIN_AVATAR_UI": "unknown"}) == "qt"
    assert resolve_avatar_window_class({"BRAIN_AVATAR_UI": "qt"}) is QtAvatarWindow

def test_qt_window_ready_is_sent_once_after_complete_runtime_setup() -> None:
    app = QApplication.instance() or QApplication([])
    observations = []

    def observe_ready(window, path, payload=None):
        assert path == '/window-ready'
        assert window.state == 'awaiting'
        assert window.bubble is not None
        assert window.controls is not None
        assert window.poll_timer.isActive()
        assert window.hover_timer.isActive()
        assert window.tail_timer.isActive()
        observations.append((path, payload))

    with (
        patch.object(QtAvatarWindow, '_post', autospec=True, side_effect=observe_ready),
        patch.object(QtAvatarWindow, '_refresh_quotas'),
    ):
        window = QtAvatarWindow(start_polling=True)
        assert observations == []
        app.processEvents()
        assert observations == [('/window-ready', {'pid': os.getpid()})]
        window._signal_window_ready()

    assert observations == [('/window-ready', {'pid': os.getpid()})]
    window.close()
    app.processEvents()

def test_qt_avatar_body_click_preserves_pause_close_and_reactions() -> None:
    """Qt delays pause-and-close so a double click remains a reaction gesture."""
    import inspect

    source = inspect.getsource(QtAvatarWindow._avatar_click)
    reaction_source = inspect.getsource(QtAvatarWindow._speak_reaction)
    assert "avatar_click_timer.isActive()" in source
    assert "_speak_reaction()" in source
    assert "ReactionIntent(reaction.message, reaction.animation)" in reaction_source
    assert "InteractionController.double_click" in reaction_source

def test_qt_single_avatar_click_stops_active_speak_and_never_replays_when_idle() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.state = "speaking"
    window.playback_active = True
    window.active_speak_id = "speak-one"
    window.current_message_id = "speak-one"
    window.active_presentation_owned = True
    with patch.object(window, "_post") as post:
        window._commit_avatar_click()
        post.assert_called_once_with("/stop-current-message")
        post.reset_mock()
        window.state = "awaiting"
        window.playback_active = False
        window.progressive_playback_active = False
        window._commit_avatar_click()
        post.assert_called_once_with("/replay", {"speakId": "speak-one"})
    window.close()

def test_qt_progressive_click_terminally_stops_without_dismiss_or_replay() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.state = 'speaking'
    window.playback_active = True
    window.progressive_playback_active = True
    window.active_speak_id = 'speak-one'
    window.active_presentation_owned = True
    with patch.object(window, '_post') as post, patch.object(window, '_dismiss_bubble') as dismiss:
        window._commit_avatar_click()
    post.assert_called_once_with('/stop-current-message')
    dismiss.assert_called_once_with()
    window.close()
    app.processEvents()

def test_qt_progressive_stop_precedes_manual_file_narration() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.state = 'speaking'
    window.playback_active = True
    window.progressive_playback_active = True
    window.current_has_embedded_file = True
    window.current_manual_speech = True
    window.active_speak_id = 'speak-one'
    window.active_presentation_owned = True
    with patch.object(window, '_post') as post:
        window._commit_avatar_click()
    post.assert_called_once_with('/stop-current-message')
    window.close()
    app.processEvents()

def test_qt_double_avatar_click_during_playback_stops_without_reaction() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.state = 'speaking'
    window.playback_active = True
    window.active_speak_id = 'speak-one'
    window.active_presentation_owned = True
    with patch.object(window, '_speak_reaction') as react, patch.object(window, '_post') as post:
        window._avatar_click()
        window._avatar_click()
    react.assert_not_called()
    post.assert_called_once_with('/stop-current-message')
    window.close()
    app.processEvents()

def test_qt_double_avatar_click_reacts_without_committing_single_click() -> None:
    """A second click cancels the delayed single action and emits exactly one reaction."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)

    with patch.object(window, "_speak_reaction") as react, patch.object(window, "_commit_avatar_click") as commit:
        window._avatar_click()
        window._avatar_click()

    react.assert_called_once_with()
    commit.assert_not_called()
    assert not window.avatar_click_timer.isActive()
    window.close()

def test_message_control_toggles_visual_without_replay() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window._set_text("Mensaje retenido", "happy", "speak-one")
    assert window.bubble.isVisible()
    with patch.object(window, "_post") as post:
        window._toggle_last_message()
        assert not window.bubble.isVisible()
        window._toggle_last_message()
    assert window.bubble.isVisible()
    post.assert_not_called()
    window.close()

def test_dismissing_muted_bubble_cancels_daemon_turn() -> None:
    """Closing a muted bubble releases its active daemon presentation."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.state = "muted_replay"
    window.current_display_text = "Mensaje muteado"
    window.current_message_id = "muted-one"
    window.active_speak_id = "muted-one"
    window.active_presentation_owned = True
    window.bubble.show()

    with patch.object(window, "_post") as post:
        window._dismiss_bubble()

    post.assert_called_once_with("/stop-current-message")
    assert not window.bubble.isVisible()
    window.close()

def test_central_control_stops_audible_or_muted_message_and_closes_bubble() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    with patch.object(window, "_post") as post:
        window.state = "speaking"
        window.playback_active = True
        window.active_speak_id = "speak-one"
        window.active_presentation_owned = True
        window.bubble.show()
        window._activate_message_control()
        assert not window.bubble.isVisible()
        window.state = "muted"
        window.playback_active = False
        window.active_speak_id = "muted-one"
        window.active_presentation_owned = True
        window.bubble.show()
        window._activate_message_control()
        assert not window.bubble.isVisible()
    assert post.call_args_list == [
        call("/stop-current-message"),
        call("/stop-current-message"),
    ]
    window.close()

def test_central_play_replays_projected_history_when_idle() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.state = "awaiting"
    window.history_browsing = True
    window.message_reveal_latched = True
    window.current_message_id = "history-one"
    window.current_audio_name = "retained-message.mp3"
    window.current_display_text = "Mensaje histórico"
    with patch.object(window, "_post") as post:
        window._activate_message_control()
    post.assert_called_once_with("/replay", {"speakId": "history-one"})
    assert window.current_message_id == "history-one"
    window.close()

def test_terminal_empty_poll_preserves_visible_projection_identity_for_replay() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.state = "awaiting"
    window._set_text("Cuarto mensaje", "happy", "speak-four", history_count=4)

    assert window.bubble.isVisible()
    assert window.current_message_id == "speak-four"
    assert window.bubble.history_label.text() == "4/4"

    window._set_text("", history_count=4)

    assert window.bubble.isVisible()
    assert window.current_display_text == "Cuarto mensaje"
    assert window.current_message_id == "speak-four"
    with patch.object(window, "_post") as post:
        window._activate_message_control()
    post.assert_called_once_with("/replay", {"speakId": "speak-four"})
    window.close()

def test_message_icon_restores_last_projection_identity_for_replay() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window._set_text("Último mensaje", "happy", "speak-last", history_count=3)
    window._dismiss_bubble()
    window.current_message_id = ""

    window._toggle_last_message()

    assert window.bubble.isVisible()
    assert window.current_message_id == "speak-last"
    with patch.object(window, "_post") as post:
        window._activate_message_control()
    post.assert_called_once_with("/replay", {"speakId": "speak-last"})
    window.close()

def test_central_control_is_wired_to_shared_stop_play_contract() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    assert window.controls.on_playback == window._activate_message_control
    window.close()


def test_backlog_clock_click_dispatches_the_backlog_action() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window.controls.set_expanded(True)
    with patch.object(window, "_open_backlog_window") as open_backlog:
        window.controls.on_backlog = open_backlog
        center = backlog_geometry(window.controls.width(), window.controls.height()).center().toPoint()
        QTest.mouseClick(window.controls, Qt.MouseButton.LeftButton, pos=center)
    open_backlog.assert_called_once_with()
    window.close()


def test_closing_real_backlog_window_does_not_close_or_reposition_avatar() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    original_geometry = window.geometry()
    controller = BacklogController(
        lambda: [ProjectView("alpha", "Alpha")],
        lambda project, statuses: [],
        lambda draft: TaskView("t1", draft.project, draft.domain, draft.title, "", draft.priority, "TODO"),
    )
    backlog = BacklogWindow(controller)
    with patch(
        "brain.presentation.avatar.qt.runtime.window.create_backlog_window",
        return_value=backlog,
    ):
        window._open_backlog_window()
    backlog.close()
    app.processEvents()
    assert app.quitOnLastWindowClosed() is False
    assert window.isVisible()
    assert window.geometry() == original_geometry
    window.close()


def test_open_backlog_tracks_runtime_theme_changes() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    backlog = Mock()
    window.backlog_window = backlog
    with patch("brain.presentation.avatar.qt.runtime.backend_adapter.urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = b'{"themeMode":"dark"}'
        window._poll()
    backlog.set_theme.assert_called_once_with("dark")
    assert window._theme_mode == "dark"
    window.close()


def test_backlog_window_is_created_once_then_refocused() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    backlog = QWidget()
    backlog.reload_projects = Mock()
    with patch(
        "brain.presentation.avatar.qt.runtime.window.create_backlog_window",
        return_value=backlog,
    ) as factory:
        window._open_backlog_window()
        window._open_backlog_window()
    factory.assert_called_once_with(theme_mode="light")
    backlog.reload_projects.assert_called_once_with()
    assert window.backlog_window is backlog
    assert backlog.isVisible()
    window.close()

def test_message_history_links_each_speak_to_its_retained_audio() -> None:
    """History records expose the audio name selected by their speak identifier."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    with patch("brain.presentation.avatar.qt.runtime.message_controller.urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = (
            b'{"speaks":[{"id":"speak-one","text":"Uno"}],'
            b'"messages":[{"speakId":"speak-one","name":"one.mp3"}]}'
        )
        history = window._message_history()
    assert history[0]["audioName"] == "one.mp3"
    window.close()

def test_qt_avatar_click_requests_manual_narration_for_active_file() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.state = 'awaiting'
    window._set_text(
        'Attached plan',
        'focused',
        'file-one',
        has_embedded_file=True,
        manual_speech=True,
    )
    with patch.object(window, '_post') as post:
        window._commit_avatar_click()
    post.assert_called_once_with('/narrate-active-file')
    assert window.bubble.isVisible()
    window.close()
    app.processEvents()

def test_qt_avatar_click_requires_both_explicit_file_flags() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.state = 'awaiting'
    with patch.object(window, '_post') as post:
        window._set_text('File-like', message_id='one', has_embedded_file=True, manual_speech=False)
        window._commit_avatar_click()
        window._set_text('Manual-like', message_id='two', has_embedded_file=False, manual_speech=True)
        window._commit_avatar_click()
    assert post.call_args_list == [
        call('/replay', {'speakId': 'one'}),
        call('/replay', {'speakId': 'two'}),
    ]
    assert call('/narrate-active-file') not in post.call_args_list
    window.close()
    app.processEvents()

def test_qt_stop_ownership_requires_active_speak_and_badge_uses_daemon_depth() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    payloads = [
        {
            'state': 'awaiting', 'activeSpeakId': '', 'muteMode': 'total',
            'queueDepth': 0, 'historyCount': 99,
        },
        {
            'state': 'muted', 'activeSpeakId': 'muted-one', 'muteMode': 'total',
            'queueDepth': 0, 'historyCount': 99,
        },
        {
            'state': 'awaiting', 'activeSpeakId': '', 'muteMode': 'total',
            'queueDepth': 0, 'historyCount': 99,
        },
        {
            'state': 'speaking', 'activeSpeakId': 'speak-two', 'muteMode': 'off',
            'playbackActive': True, 'queueDepth': 2, 'historyCount': 99,
        },
    ]
    with patch('brain.presentation.avatar.qt.runtime.backend_adapter.urlopen') as urlopen:
        read = urlopen.return_value.__enter__.return_value.read
        read.side_effect = [json.dumps(payload).encode('utf-8') for payload in payloads]
        window._poll()
        assert window.controls.playing is False
        assert window.controls.queue_depth == 0
        window._poll()
        assert window.controls.playing is True
        assert window.active_speak_id == 'muted-one'
        assert window.controls.queue_depth == 0
        window._poll()
        assert window.controls.playing is False
        assert window.active_speak_id == ''
        window._poll()
        assert window.controls.playing is True
        assert window.active_speak_id == 'speak-two'
        assert window.controls.queue_depth == 2
    window.close()
    app.processEvents()

def test_qt_status_projects_only_logical_message_counts() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    payload = {
        'state': 'working',
        'activeSpeakId': 'logical-one',
        'displayText': 'Logical message',
        'playbackActive': False,
        'progressivePlaybackActive': True,
        'queueDepth': 2,
        'historyCount': 3,
        'internalChunkCount': 19,
        'audioBufferCount': 11,
    }
    response = patch('brain.presentation.avatar.qt.runtime.backend_adapter.urlopen')
    with response as urlopen:
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode('utf-8')
        window._poll()
        window._poll()
    assert window.controls.queue_depth == 2
    assert window.history_count == 3
    assert window.progressive_playback_active is True
    window.close()
    app.processEvents()

def test_qt_history_file_click_does_not_narrate_a_different_active_file() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.state = 'awaiting'
    window.current_has_embedded_file = True
    window.current_manual_speech = True
    window.progressive_playback_active = True
    window.active_speak_id = 'speak-live'
    window.active_presentation_owned = True
    window.history_browsing = True
    with patch.object(window, '_post') as post:
        window._commit_avatar_click()
    post.assert_called_once_with('/stop-current-message')
    window.close()
    app.processEvents()

def test_qt_muted_file_click_terminally_stops_current_message() -> None:
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.state = 'muted'
    window._set_text(
        'Attached plan',
        'focused',
        'file-one',
        has_embedded_file=True,
        manual_speech=True,
    )
    window.active_speak_id = 'file-one'
    window.active_presentation_owned = True
    with patch.object(window, '_post') as post:
        window._commit_avatar_click()
    post.assert_called_once_with('/stop-current-message')
    assert not window.bubble.isVisible()
    window.close()
    app.processEvents()


def test_picture_control_click_dispatches_capture_action() -> None:
    """Clicking the picture control invokes only the capture callback."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    window.show()
    window.controls.set_expanded(True)
    with patch.object(window, "_open_capture_form") as open_capture:
        window.controls.on_capture = open_capture
        center = capture_geometry(window.controls.width(), window.controls.height()).center().toPoint()
        QTest.mouseClick(window.controls, Qt.MouseButton.LeftButton, pos=center)

    open_capture.assert_called_once_with()
    window.close()


def test_avatar_capture_handoff_leaves_task_list_hidden() -> None:
    """Direct capture uses the backlog coordinator without showing its task list."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    backlog = Mock()
    window.backlog_window = backlog

    window._open_capture_form()

    backlog.reload_projects.assert_called_once_with()
    backlog.show.assert_not_called()
    backlog.hide.assert_called_once_with()
    backlog.open_capture_form.assert_called_once_with()
    window.close()


def test_clock_action_shows_the_backlog_task_list() -> None:
    """Clock mode retains the visible task-list backlog behavior."""
    app = QApplication.instance() or QApplication([])
    window = QtAvatarWindow(start_polling=False)
    backlog = Mock()
    window.backlog_window = backlog

    window._open_backlog_window()

    backlog.reload_projects.assert_called_once_with()
    backlog.show_backlog_window.assert_called_once_with()
    backlog.open_capture_form.assert_not_called()
    window.close()
