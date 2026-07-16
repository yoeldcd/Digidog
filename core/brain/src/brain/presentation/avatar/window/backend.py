# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Safe presentation-backend selection for the avatar process."""
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Type


def requested_avatar_backend(environ: Mapping[str, str] | None = None) -> str:
    """Return a normalized requested backend; Tk remains the safe default."""
    value = (environ or os.environ).get("BRAIN_AVATAR_UI", "qt").strip().lower()
    return value if value in {"tk", "qt"} else "qt"


def resolve_avatar_window_class(environ: Mapping[str, str] | None = None) -> Type:
    """Resolve Qt when its full window exists, otherwise preserve the Tk runtime."""
    if requested_avatar_backend(environ) == "qt":
        try:
            from brain.presentation.avatar.qt.window import QtAvatarWindow
            return QtAvatarWindow
        except (ImportError, ModuleNotFoundError):
            pass
    from brain.presentation.avatar.tk.window import AvatarWindow
    return AvatarWindow
