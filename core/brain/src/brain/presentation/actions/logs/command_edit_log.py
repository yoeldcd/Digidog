# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""CLI action for editing workspace log entries."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
import os
from pathlib import Path

# Application Modules Imports
from brain.application.logs.edit_service import EditLogError, EditLogRequest, edit_log_entry
from brain.presentation.terminal import log_step, render_placeholders


def _first_present(*values: str | None) -> str | None:
    """
    Return the first provided CLI value.

    Args:
        *values (str | None): Candidate values in priority order.

    Returns:
        str | None: First non-None value.
    """
    for value in values:
        if value is not None:
            return value
    return None


def handle(args: argparse.Namespace) -> int:
    """
    Edit one workspace log entry.

    Args:
        args (argparse.Namespace): Parsed CLI arguments.

    Returns:
        int: Process exit code.
    """
    color_enabled: bool = getattr(args, "color", False)
    log_step(args, "[1/3] Parsing and validating inputs...")
    try:
        timestamp: str | None = _first_present(args.datetime, args.timestamp)
        if timestamp is None:
            raise EditLogError("Datetime must be provided via --datetime or compact positional form.")

        workspace_root: Path = Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve()
        request = EditLogRequest(
            timestamp=timestamp,
            log_domain=_first_present(args.log_domain, args.domain),
            title=_first_present(args.title, args.compact_title),
            change_type=_first_present(args.type, args.compact_type),
            why=_first_present(args.why, args.compact_why),
            description=_first_present(args.desc, args.compact_desc),
            impact=_first_present(args.impact, args.compact_impact),
        )
        log_step(args, "[2/3] Applying log entry update...")
        result = edit_log_entry(workspace_root=workspace_root, request=request)
        log_step(args, "[3/3] Updating logs index...")
        print(render_placeholders(f"Log entry indexed: `{result.read_command}`", color_enabled))
        from brain.application.logs.store import get_log_entry_by_timestamp

        entry = get_log_entry_by_timestamp(workspace_root=workspace_root, timestamp=result.timestamp)
        args.json_payload = {
            "ok": True,
            "command": "edit-log",
            "entry": {
                "timestamp": entry.timestamp,
                "domain": entry.domain,
                "title": entry.title,
                "changeType": entry.change_type,
                "why": entry.why,
                "description": entry.description,
                "impact": entry.impact,
                "readCommand": result.read_command,
                "path": result.log_file.as_posix(),
            } if entry is not None else None,
        }
        return 0
    except (EditLogError, ValueError) as exc:
        print(render_placeholders(f"__RED__Error: {exc}__RESET__", color_enabled))
        return 1
    except Exception as exc:
        print(render_placeholders(f"__RED__Error: {exc}__RESET__", color_enabled))
        return 1
