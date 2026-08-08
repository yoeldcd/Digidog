"""Avatar window-process lifecycle infrastructure."""

from brain.infrastructure.avatar.process.avatar_process import AvatarProcessSupervisor
from brain.infrastructure.avatar.process.avatar_supervision import (
    SupervisedVoiceRuntime,
    run_avatar_supervision,
    supervise_avatar_window,
)

__all__ = [
    "AvatarProcessSupervisor",
    "SupervisedVoiceRuntime",
    "run_avatar_supervision",
    "supervise_avatar_window",
]