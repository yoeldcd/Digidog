# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Coordinate the validated finalization of one workspace task."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from brain.application.backlog.service import set_backlog_task_status
from brain.application.logs.append_service import AppendLogRequest, append_log_entry
from brain.application.logs.store import refresh_log_index


def handle(args) -> int:
    """Stage explicit files, record the change, and complete its backlog task."""
    workspace_root = Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve()
    try:
        stage_paths = _validated_stage_paths(workspace_root, args.stage)
        subprocess.run(
            ["git", "add", "--", *stage_paths],
            cwd=workspace_root,
            check=True,
            capture_output=True,
            text=True,
        )
        result = append_log_entry(
            workspace_root=workspace_root,
            request=AppendLogRequest(
                log_domain=args.domain,
                title=args.title,
                change_type=args.change_type,
                why=args.why,
                description=args.description,
                impact=args.impact,
            ),
        )
        refresh_log_index(workspace_root=workspace_root)
        task = set_backlog_task_status(workspace_root=workspace_root, task_id=args.task_id, status="DONE")
        print(f"[SUCCESS] {task.task_id} completed; log `{result.read_command}`; {len(stage_paths)} paths staged.")
        args.narration_timestamp = result.timestamp
        args.narration_log_summary = args.description
        args.json_payload = {
            "ok": True,
            "command": "complete-work",
            "task": {**task.as_mapping(), "domain": task.domain},
            "log": {
                "timestamp": result.timestamp,
                "readCommand": result.read_command,
                "path": result.log_file.as_posix(),
                "domain": args.domain,
                "title": args.title,
                "changeType": args.change_type,
            },
            "stagedPaths": stage_paths,
        }
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Error completing work: {exc}")
        return 1


def _validated_stage_paths(workspace_root: Path, requested_paths: list[str]) -> list[str]:
    """Validate explicit stage paths and return repository-relative strings."""
    validated: list[str] = []
    for requested_path in requested_paths:
        candidate = (workspace_root / requested_path).resolve()
        try:
            relative = candidate.relative_to(workspace_root)
        except ValueError as exc:
            raise ValueError(f"Stage path escapes workspace: {requested_path}") from exc
        if not candidate.exists():
            raise ValueError(f"Stage path does not exist: {requested_path}")
        validated.append(relative.as_posix())
    if not validated:
        raise ValueError("At least one explicit stage path is required.")
    return validated
