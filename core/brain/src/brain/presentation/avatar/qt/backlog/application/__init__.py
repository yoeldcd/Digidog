"""Application coordination exports for the native Qt backlog."""

from importlib import import_module

__all__ = ["BacklogActionError", "BacklogController", "create_backlog_window"]
_EXPORTS = {
    "BacklogActionError": ("brain.presentation.avatar.qt.backlog.application.controller", "BacklogActionError"),
    "BacklogController": ("brain.presentation.avatar.qt.backlog.application.controller", "BacklogController"),
    "create_backlog_window": ("brain.presentation.avatar.qt.backlog.application.composition", "create_backlog_window"),
}


def __getattr__(name: str) -> object:
    """Resolve application exports lazily to keep composition and view acyclic."""
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(target[0]), target[1])
    globals()[name] = value
    return value
