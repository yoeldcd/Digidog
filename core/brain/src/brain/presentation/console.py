"""Console runtime helpers for the Brain CLI entrypoint."""

from __future__ import annotations

import sys


def configure_utf8_console() -> None:
    """Configure Windows console streams and ANSI support when available."""
    if sys.platform != "win32":
        return

    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        stdout_handle = kernel32.GetStdHandle(-11)
        console_mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(stdout_handle, ctypes.byref(console_mode)):
            kernel32.SetConsoleMode(stdout_handle, console_mode.value | 0x0004)
    except Exception:
        pass
