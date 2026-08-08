# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Avatar window presentation constants and asset resolution."""

from pathlib import Path
import re

from brain.infrastructure.runtime.paths import get_avatar_assets_dir

INITIAL_WIDTH = 270
INITIAL_HEIGHT = 360
MIN_WIDTH = 150
MIN_HEIGHT = 200
SCREEN_MARGIN = 20
POLL_INTERVAL_MS = 250
DAEMON_LOSS_GRACE_SECONDS = 2.0
# Deliberately synthetic chroma key; dark keys punch holes in dark GIF pixels.
TRANSPARENT_COLOR = "#00ff01"


def avatar_asset(state: str, fallback_state: str = "speaking") -> Path:
    """Resolve a user-owned avatar GIF with an explicit state fallback.

    Args:
        state (str): Requested avatar state name.
        fallback_state (str): Safe state used when the requested asset is absent.

    Returns:
        Path: Existing state asset or the canonical speaking asset path.
    """
    root = get_avatar_assets_dir()
    normalized_state = (state or "").strip().lower()
    if re.fullmatch(r"[a-z0-9_-]+\.gif", normalized_state):
        candidate = root / normalized_state
    else:
        safe_state = normalized_state if re.fullmatch(r"[a-z0-9_-]+", normalized_state) else "speaking"
        candidate = root / f"avatar_{safe_state}.gif"
    if candidate.is_file():
        return candidate
    safe_fallback = fallback_state if re.fullmatch(r"[a-z0-9_-]+", fallback_state or "") else "speaking"
    fallback = root / f"avatar_{safe_fallback}.gif"
    return fallback if fallback.is_file() else root / "avatar_speaking.gif"


def default_geometry(screen_width: int) -> str:
    """Build initial upper-right window geometry.

    Args:
        screen_width (int): Available screen width in pixels.

    Returns:
        str: Tk-compatible window geometry string.
    """
    x = max(SCREEN_MARGIN, screen_width - INITIAL_WIDTH - SCREEN_MARGIN)
    return f"{INITIAL_WIDTH}x{INITIAL_HEIGHT}+{x}+{SCREEN_MARGIN + 120}"
