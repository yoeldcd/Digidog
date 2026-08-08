# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Safe presentation-backend selection for the avatar process."""
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Type


def requested_avatar_backend(environ: Mapping[str, str] | None = None) -> str:
    """Resolve the normalized requested presentation backend.

    Args:
        environ (Mapping[str, str] | None): Environment override, or ``None``
            for process environment variables.

    Returns:
        str: Supported backend name, defaulting to ``qt``.
    """
    value = (environ or os.environ).get("BRAIN_AVATAR_UI", "qt").strip().lower()
    return value if value in {"tk", "qt"} else "qt"


def resolve_avatar_window_class(environ: Mapping[str, str] | None = None) -> Type:
    """Resolve Qt when available, otherwise preserve the Tk runtime.

    Args:
        environ (Mapping[str, str] | None): Environment override for backend
            selection.

    Returns:
        Type: Concrete avatar window class.
    """
    if requested_avatar_backend(environ) == "qt":
        try:
            from brain.presentation.avatar.qt.runtime.window import QtAvatarWindow
            return QtAvatarWindow
        except (ImportError, ModuleNotFoundError):
            pass
    from brain.presentation.avatar.tk.avatar.window import AvatarWindow
    return AvatarWindow
