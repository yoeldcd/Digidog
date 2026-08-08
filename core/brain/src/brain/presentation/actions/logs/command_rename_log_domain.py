"""CLI action for renaming a log domain subtree."""

from __future__ import annotations

# Standard Libraries Imports
from dataclasses import asdict
import os
from pathlib import Path
import sys

# Application Modules Imports
from brain.application.domains.rename_service import rename_log_domain


def handle(args) -> int:
    """
    Rename matching log domains and expose a structured result.

    Args:
        args: Parsed CLI namespace containing source, target, and exact fields.

    Returns:
        int: Zero on success or one when domain validation fails.
    """
    try:
        result = rename_log_domain(
            workspace_root=Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve(),
            source=args.source,
            target=args.target,
            exact=bool(args.exact),
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    args.json_payload = {"ok": True, "command": "rename-log-domain", "rename": asdict(result)}
    print(f"[SUCCESS] Renamed {result.changed} log entries from {result.source} to {result.target}.")
    return 0
