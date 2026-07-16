# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""CLI action for validating and appending one workspace log entry."""

import argparse
import os
from pathlib import Path

# Application Modules Imports
from brain.application.logs.append_service import AppendLogError, AppendLogRequest, append_log_entry
from brain.presentation.terminal import log_step, render_placeholders


def _first_present(*values: str | None) -> str | None:
    """Return the first provided CLI value."""
    for value in values:
        if value is not None:
            return value
    return None


def handle(args: argparse.Namespace) -> int:
    """Append log entry."""
    color_enabled = getattr(args, "color", False)
    log_step(args, "[1/3] Parsing and validating inputs...")
    try:
        workspace_root = Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve()
        log_domain = _first_present(args.log_domain, args.domain)
        title = _first_present(args.title, args.compact_title)
        change_type_raw = _first_present(args.type, args.compact_type)
        why = _first_present(args.why, args.compact_why)
        desc = _first_present(args.desc, args.compact_desc)
        impact = _first_present(args.impact, args.compact_impact)

        required_values = {
            "domain": log_domain,
            "title": title,
            "type": change_type_raw,
            "why": why,
            "desc": desc,
            "impact": impact,
        }
        missing = [name for name, value in required_values.items() if value is None]
        if missing:
            msg = f"__RED__Error: Missing required log values: {', '.join(missing)}.__RESET__"
            print(render_placeholders(msg, color_enabled))
            return 1

        log_step(args, "[2/3] Writing log entry to SQLite...")
        request = AppendLogRequest(
            log_domain=log_domain,
            title=title,
            change_type=change_type_raw,
            why=why,
            description=desc,
            impact=impact,
            timestamp=args.datetime,
        )
        result = append_log_entry(workspace_root=workspace_root, request=request)
        log_step(args, "[3/3] Updating logs index cache...")
        msg = f"Log entry indexed: `{result.read_command}`"

        print(render_placeholders(msg, color_enabled))
        args.json_payload = {
            "ok": True,
            "command": "append-log",
            "entry": {
                "timestamp": result.timestamp,
                "domain": request.log_domain,
                "title": request.title,
                "changeType": request.change_type,
                "why": request.why,
                "description": request.description,
                "impact": request.impact,
                "readCommand": result.read_command,
                "path": result.log_file.as_posix(),
            },
        }
        return 0
    except (AppendLogError, ValueError) as exc:
        msg = f"__RED__Error: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled))
        return 1
