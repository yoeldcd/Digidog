"""CLI launcher for create-agent-directory."""

from __future__ import annotations

import sys
from pathlib import Path

UTILITY_ROOT = Path(__file__).resolve().parent
if str(UTILITY_ROOT) not in sys.path:
    sys.path.insert(0, str(UTILITY_ROOT))

from src.runtime import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], Path(__file__)))