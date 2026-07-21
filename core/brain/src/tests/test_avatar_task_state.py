# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Coverage for backlog-driven avatar ambient states."""

from argparse import Namespace
from unittest.mock import patch

from brain.infrastructure.voice.daemon import VoiceMemory
from brain.infrastructure.voice.signals import VoiceSignalService
from brain.presentation.avatar.tk.window import AvatarWindow
from brain.presentation.router.services.command_router_service import dispatch_command


def test_voice_memory_restores_ambient_state_after_transient_speaking() -> None:
    memory = VoiceMemory()

    assert memory.set_ambient_state("working") == "working"
    assert memory.status()["ambientState"] == "working"
    memory.set_state("speaking", "Estoy trabajando", "focused")
    memory.set_state("awaiting")
    assert memory.status()["state"] == "working"

    memory.set_state("speaking", "Estoy terminando", "happy")
    memory.set_ambient_state("awaiting")

    assert memory.status()["state"] == "speaking"
    memory.set_state("awaiting")
    assert memory.status()["state"] == "awaiting"


def test_voice_memory_rejects_unknown_ambient_states() -> None:
    try:
        VoiceMemory().set_ambient_state("sleeping")
    except ValueError as exc:
        assert "Unsupported ambient avatar state" in str(exc)
    else:
        raise AssertionError("An unknown ambient state must be rejected")


def test_avatar_resolves_working_with_awaiting_fallback() -> None:
    window = object.__new__(AvatarWindow)
    window.awaiting_quota_animation = ""

    assert window._animation_for_state("working", "") == ("working", "awaiting")
    assert window._animation_for_state("awaiting", "") == ("awaiting", "awaiting")


def test_task_signal_maps_working_and_completion_states() -> None:
    with patch("brain.infrastructure.voice.signals.VoiceService") as voice_service:
        service = VoiceSignalService()
        service.sync_task_state("set-task-status", Namespace(status="WORKING"))
        service.sync_task_state("task-finished", Namespace())
        service.sync_task_state("complete-work", Namespace())

    assert [call.args[0] for call in voice_service.return_value.set_ambient_state.call_args_list] == [
        "working",
        "awaiting",
        "awaiting",
    ]


def test_no_speak_still_synchronizes_successful_task_state() -> None:
    args = Namespace(command="set-task-status", no_speak=True, status="WORKING")
    with (
        patch(
            "brain.presentation.router.services.command_router_service.get_action_handler",
            return_value=lambda _args: 0,
        ),
        patch("brain.presentation.router.services.command_router_service.VoiceSignalService") as service,
    ):
        assert dispatch_command(args) == 0

    service.return_value.sync_task_state.assert_called_once_with("set-task-status", args)
