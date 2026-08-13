"""CLI action for renaming a backlog domain subtree."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
from dataclasses import asdict
import os
from pathlib import Path
import sys

# Application Modules Imports
from brain.application.domains.rename_service import rename_backlog_domain
from brain.infrastructure.runtime.paths import get_workspace_root


def handle(args: argparse.Namespace) -> int:
    """
    Rename matching backlog domains and expose a structured result.

    Args:
        args: Parsed CLI namespace containing source, target, and exact fields.

    Returns:
        int: Zero on success or one when domain validation fails.
    """
    try:
        result = rename_backlog_domain(
            workspace_root=get_workspace_root(),
            source=args.source,
            target=args.target,
            exact=bool(args.exact),
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    args.json_payload = {"ok": True, "command": "rename-task-domain", "rename": asdict(result)}
    print(f"[SUCCESS] Renamed {result.changed} backlog tasks from {result.source} to {result.target}.")
    return 0
