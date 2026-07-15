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
    """Resolve one user-owned avatar GIF with an explicit state fallback."""
    safe_state = state if re.fullmatch(r"[a-z0-9_-]+", state or "") else "speaking"
    root = get_avatar_assets_dir()
    candidate = root / f"avatar_{safe_state}.gif"
    if candidate.is_file():
        return candidate
    safe_fallback = fallback_state if re.fullmatch(r"[a-z0-9_-]+", fallback_state or "") else "speaking"
    fallback = root / f"avatar_{safe_fallback}.gif"
    return fallback if fallback.is_file() else root / "avatar_speaking.gif"


def default_geometry(screen_width: int) -> str:
    """Place the initial window in the upper-right corner."""
    x = max(SCREEN_MARGIN, screen_width - INITIAL_WIDTH - SCREEN_MARGIN)
    return f"{INITIAL_WIDTH}x{INITIAL_HEIGHT}+{x}+{SCREEN_MARGIN + 120}"
