# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Architecture and shared-contract tests for the decomposed Tk adapter."""
from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import Mock

from brain.presentation.avatar.interactivity.history_controller import HistoryMessage
from brain.presentation.avatar.interactivity.presentation_state import AvatarRuntimeState, ProjectedMessageState
from brain.presentation.avatar.tk.controls.view import TkControlsMixin
from brain.presentation.avatar.tk.runtime.message import TkMessageController
from brain.presentation.avatar.tk.runtime.adapter import TkRuntimeAdapterMixin
from brain.presentation.avatar.tk.avatar import AvatarWindow


TK_PACKAGE = Path(__file__).parents[1] / "brain" / "presentation" / "avatar" / "tk"


def test_tk_production_modules_stay_below_physical_line_limit() -> None:
    for path in TK_PACKAGE.rglob("*.py"):
        assert len(path.read_text(encoding="utf-8").splitlines()) < 500, path


def test_tk_dependency_direction_never_imports_qt() -> None:
    for path in TK_PACKAGE.rglob("*.py"):
        assert "brain.presentation.avatar.qt" not in path.read_text(encoding="utf-8"), path


def test_tk_window_is_a_thin_composition_root() -> None:
    source = inspect.getsource(AvatarWindow)
    assert len(source.splitlines()) < 150
    assert "TkDaemonAdapter()" in source
    assert "TkMessageController()" in source
    assert "QuotaThresholdTracker()" in source


def test_tk_message_controller_keeps_terminal_identity_for_replay() -> None:
    controller = TkMessageController()
    rendered = Mock()
    active = ProjectedMessageState(
        runtime_state=AvatarRuntimeState.SPEAKING,
        active_speak_id="speak-four",
        display_text="Cuarto",
        playback_active=True,
        history_count=4,
    )
    controller.apply(active, rendered)
    controller.apply(ProjectedMessageState(history_count=4), rendered)
    assert controller.replay_target().speak_id == "speak-four"
    assert rendered.call_args_list[-1].args == ("", "")


def test_tk_message_history_uses_shared_chronological_numbering() -> None:
    controller = TkMessageController()
    history = controller.retained_history({
        "speaks": [
            {"id": "four", "displayText": "Cuarto"},
            {"id": "three", "displayText": "Tercero"},
        ],
        "messages": [{"speakId": "four", "name": "four.mp3"}],
    })
    newest = history.newest()
    older = history.navigate("four", -1)
    assert newest is not None and (newest.chronological_index, newest.total) == (2, 2)
    assert newest.message.audio_name == "four.mp3"
    assert older is not None and (older.chronological_index, older.total) == (1, 2)


def test_tk_runtime_switches_speaking_animation_only_for_audible_playback() -> None:
    runtime = object.__new__(AvatarWindow)
    runtime.awaiting_quota_animation = ""
    runtime.presentation = ProjectedMessageState(
        runtime_state=AvatarRuntimeState.PREPARING,
        active_speak_id="one",
        processing=True,
    )
    assert runtime._animation_for_state("preparing", "happy") == ("awaiting", "awaiting")
    runtime.presentation = ProjectedMessageState(
        runtime_state=AvatarRuntimeState.SPEAKING,
        active_speak_id="one",
        playback_active=True,
    )
    assert runtime._animation_for_state("speaking", "happy") == ("happy", "speaking")


def test_tk_processing_indicator_obeys_render_flag_only() -> None:
    preparing = ProjectedMessageState(runtime_state=AvatarRuntimeState.PREPARING)
    rendering = ProjectedMessageState(runtime_state=AvatarRuntimeState.AWAITING, processing=True)
    assert preparing.processing_indicator_active is False
    assert rendering.processing_indicator_active is True
    assert "presentation.processing_indicator_active" in inspect.getsource(TkControlsMixin._layout_controls)


def test_tk_top_center_bottom_zones_have_distinct_bindings() -> None:
    build = inspect.getsource(TkControlsMixin._build_controls)
    click = inspect.getsource(TkControlsMixin._label_click)
    assert "self.pin =" in build and "self.message =" in build and "self.processing =" in build
    assert "playback_button_geometry" in click and "mute_button_geometry" in click
    assert "self._avatar_click(event)" in click


def test_tk_window_ready_is_emitted_after_idle_setup() -> None:
    assert "after_idle(self._signal_window_ready)" in inspect.getsource(AvatarWindow.__init__)
    assert 'self.transport.post("/window-ready", {"pid": os.getpid()})' in inspect.getsource(
        TkRuntimeAdapterMixin._signal_window_ready
    )