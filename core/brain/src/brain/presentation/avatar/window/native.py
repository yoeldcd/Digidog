# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Native priority controls for borderless avatar windows."""
from __future__ import annotations

import ctypes
import sys
import tkinter as tk


class NativeWindowPriority:
    """Apply reliable Win32 z-order semantics without activating the window.

    Attributes:
        HWND_TOPMOST (int): Win32 handle constant positioning window above all non-topmost windows.
        HWND_NOTOPMOST (int): Win32 handle constant placing window behind all topmost windows.
        SW_SHOWNOACTIVATE (int): Win32 ShowWindow flag displaying window in current size and position without activation.
        SWP_NOSIZE (int): Win32 SetWindowPos flag retaining current size.
        SWP_NOMOVE (int): Win32 SetWindowPos flag retaining current position.
        SWP_NOACTIVATE (int): Win32 SetWindowPos flag retaining current activation.
        SWP_SHOWWINDOW (int): Win32 SetWindowPos flag displaying window.
        GA_ROOT (int): Win32 GetAncestor flag retrieving root window handle.
    """

    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SW_SHOWNOACTIVATE = 4
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040
    GA_ROOT = 2

    @classmethod
    def apply(cls, window: tk.Misc, topmost: bool, show: bool = False) -> bool:
        """Set native topmost state without allowing Win32 failures to kill Tk.

        Args:
            window (tk.Misc): Tk window receiving z-order changes.
            topmost (bool): Whether the window should stay above normal windows.
            show (bool): Whether to reveal the window without activation.

        Returns:
            bool: Whether the requested state was applied successfully.
        """
        try:
            window.attributes("-topmost", topmost)
        except tk.TclError:
            return False

        if sys.platform != "win32":
            if show:
                window.deiconify()
                window.lift()

            return True

        try:
            window.update_idletasks()
            user32 = ctypes.windll.user32
            hwnd = user32.GetAncestor(window.winfo_id(), cls.GA_ROOT) or window.winfo_id()

            if show:
                user32.ShowWindow(hwnd, cls.SW_SHOWNOACTIVATE)

            flags = cls.SWP_NOSIZE | cls.SWP_NOMOVE | cls.SWP_NOACTIVATE

            if show:
                flags |= cls.SWP_SHOWWINDOW

            insert_after = cls.HWND_TOPMOST if topmost else cls.HWND_NOTOPMOST

            return bool(user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, flags))

        except (AttributeError, OSError, tk.TclError):
            return False

