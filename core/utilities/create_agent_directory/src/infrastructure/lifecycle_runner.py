"""Run agent lifecycle subprocesses through one checked adapter."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence


def run_lifecycle(command: Sequence[str], cwd: Path | None = None) -> None:
    """Run one lifecycle command with consistent failure propagation."""
    subprocess.run(tuple(command), cwd=cwd, check=True)