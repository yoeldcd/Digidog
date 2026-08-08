# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Kernel-owned singleton leases for local voice processes."""

from __future__ import annotations

import ctypes
import hashlib
import sys
from pathlib import Path

from brain.infrastructure.runtime.paths import get_core_root


ERROR_ALREADY_EXISTS = 183


def core_runtime_id(core_root: Path | None = None) -> str:
    """Build a stable opaque identifier for one physical agent core.

    Args:
        core_root (Path | None): Core root override, or ``None`` for discovery.

    Returns:
        str: Sixteen-character hash identifying the normalized core path.
    """
    normalized = get_core_root(core_root=core_root).as_posix().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def core_process_lease_name(role: str, core_root: Path | None = None) -> str:
    """Build a Windows lease name isolated by core and process role.

    Args:
        role (str): Logical process role used in the lease namespace.
        core_root (Path | None): Core root override, or ``None`` for discovery.

    Returns:
        str: Windows local mutex name.

    Raises:
        ValueError: If ``role`` contains no alphanumeric characters.
    """
    safe_role = "".join(character if character.isalnum() else "-" for character in role).strip("-")
    if not safe_role:
        raise ValueError("process lease role cannot be empty")
    return rf"Local\Brain-{safe_role}-{core_runtime_id(core_root=core_root)}"


class ProcessLease:
    """Hold one named Windows kernel object for the process lifetime."""

    def __init__(self, name: str) -> None:
        """Create an unacquired lease with a stable cross-process name."""
        self._name = name
        self._handle: int | None = None
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True) if sys.platform == "win32" else None

    def acquire(self) -> bool:
        """Acquire the lease unless another process already owns its name.

        Returns:
            bool: ``True`` when this process owns the lease; otherwise ``False``.

        Raises:
            ctypes.WinError: If Windows cannot create the named mutex.
        """
        if self._handle is not None:
            return True
        if self._kernel32 is None:
            self._handle = 1
            return True
        self._kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = self._kernel32.CreateMutexW(None, False, self._name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            self._kernel32.CloseHandle(handle)
            return False
        self._handle = int(handle)
        return True

    def close(self) -> None:
        """Release the named object; process termination also releases it automatically."""
        if self._handle is None:
            return
        if self._kernel32 is not None:
            self._kernel32.CloseHandle(self._handle)
        self._handle = None
