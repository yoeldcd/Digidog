# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Executable entrypoint for the voice avatar window."""
import os
import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[4]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from brain.presentation.avatar.window.backend import resolve_avatar_window_class  # noqa: E402
from brain.infrastructure.voice.process_lease import ProcessLease, core_process_lease_name  # noqa: E402


def run_avatar_window() -> None:
    """Run the selected backend and recover with Tk if Qt cannot start."""
    window_class = resolve_avatar_window_class()
    try:
        window_class().run()
    except Exception:
        from brain.presentation.avatar.tk.window import AvatarWindow
        if window_class is AvatarWindow:
            raise
        AvatarWindow().run()

if __name__ == "__main__":
    daemon_instance_id = os.environ.get("BRAIN_VOICE_DAEMON_INSTANCE_ID", "")
    lease = ProcessLease(core_process_lease_name("voice-avatar-window"))
    if lease.acquire():
        try:
            run_avatar_window()
        finally:
            lease.close()
