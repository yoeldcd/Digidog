# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Avatar child-process supervision isolated from daemon composition."""

from __future__ import annotations

import threading
from typing import Protocol

from brain.infrastructure.avatar.process.avatar_process import AvatarProcessSupervisor


class SupervisedVoiceRuntime(Protocol):
    """Narrow state port required by avatar-process supervision."""

    window_supervisor: AvatarProcessSupervisor | None
    current_window_pid: int | None

    def bind_window_supervisor(self, supervisor: AvatarProcessSupervisor) -> None: ...
    def register_window_process(self, pid: int) -> None: ...
    def prepare_for_window_spawn(self) -> None: ...
    def stop_window_owned_speak(self) -> None: ...
    def record_supervision_error(self, error: Exception) -> None: ...


def supervise_avatar_window(memory: SupervisedVoiceRuntime, supervisor: AvatarProcessSupervisor) -> int:
    """Validate a child or atomically invalidate its lease before respawn."""
    if memory.window_supervisor is not supervisor:
        memory.bind_window_supervisor(supervisor)
    live_pid = supervisor.pid
    if live_pid is not None:
        if memory.current_window_pid != live_pid:
            memory.register_window_process(live_pid)
        return live_pid
    memory.prepare_for_window_spawn()
    memory.stop_window_owned_speak()
    replacement_pid = supervisor.ensure_running()
    memory.register_window_process(replacement_pid)
    return replacement_pid


def run_avatar_supervision(
    memory: SupervisedVoiceRuntime,
    supervisor: AvatarProcessSupervisor,
    stop_event: threading.Event,
    poll_seconds: float = 0.05,
) -> None:
    """Poll child lifecycle independently from blocking HTTP request handling."""
    interval = max(0.01, poll_seconds)
    consecutive_failures = 0
    while not stop_event.wait(interval):
        try:
            supervise_avatar_window(memory, supervisor)
            consecutive_failures = 0
        except Exception as exc:
            memory.prepare_for_window_spawn()
            memory.stop_window_owned_speak()
            memory.record_supervision_error(exc)
            consecutive_failures = min(6, consecutive_failures + 1)
            if stop_event.wait(min(1.0, interval * (2 ** consecutive_failures))):
                return