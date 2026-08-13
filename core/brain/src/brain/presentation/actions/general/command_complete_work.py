# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Coordinate the validated finalization of one workspace task."""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from brain.application.backlog.models import BacklogTask
from brain.application.backlog.service import get_backlog_task, set_backlog_task_status
from brain.application.logs.append_service import AppendLogRequest, append_log_entry
from brain.application.logs.store import refresh_log_index
from brain.infrastructure.runtime.paths import get_workspace_root


@dataclass(slots=True, frozen=True)
class CompletionMetadata:
    """Resolved log metadata for one completed backlog task.

    Attributes:
        domain: `str`. Dot-notated log domain.
        title: `str`. Human-readable log title.
        change_type: `str`. Canonical change classification requested by the caller.
        why: `str`. Motivation inherited from the task or explicitly overridden.
        description: `str`. Concise implementation summary supplied at completion.
        impact: `str`. Observable result of the completed work.
    """

    domain: str
    title: str
    change_type: str
    why: str
    description: str
    impact: str


def handle(args: argparse.Namespace) -> int:
    """Stage explicit files, record the change, and complete a backlog task.

    Args:
        args: `argparse.Namespace`. Parsed completion and explicit staging-path arguments.

    Returns:
        int: Zero on completed work; otherwise one.
    """
    workspace_root = get_workspace_root()
    try:
        pending_task = get_backlog_task(workspace_root=workspace_root, task_id=args.task_id)
        metadata = _resolve_completion_metadata(task=pending_task, args=args)
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
                log_domain=metadata.domain,
                title=metadata.title,
                change_type=metadata.change_type,
                why=metadata.why,
                description=metadata.description,
                impact=metadata.impact,
            ),
        )
        refresh_log_index(workspace_root=workspace_root)
        task = set_backlog_task_status(workspace_root=workspace_root, task_id=args.task_id, status="DONE")
        print(f"[SUCCESS] {task.task_id} completed; log `{result.read_command}`; {len(stage_paths)} paths staged.")
        args.narration_timestamp = result.timestamp
        args.narration_log_summary = metadata.description
        navigation_path = f"/?section=backlog&task={task.task_id}"
        args.json_payload = {
            "ok": True,
            "command": "complete-work",
            "task": {**task.as_mapping(), "domain": task.domain},
            "log": {
                "timestamp": result.timestamp,
                "readCommand": result.read_command,
                "domain": metadata.domain,
                "domainChain": [part for part in metadata.domain.split(".") if part],
                "title": metadata.title,
                "changeType": metadata.change_type,
            },
            "navigation": {
                "surface": "backlog",
                "taskId": task.task_id,
                "path": navigation_path,
            },
            "stagedPaths": stage_paths,
        }
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Error completing work: {exc}")
        return 1


def _resolve_completion_metadata(task: BacklogTask, args: argparse.Namespace) -> CompletionMetadata:
    """Resolve compact or legacy CLI values into canonical completion metadata.

    Args:
        task: `BacklogTask`. Persistent task supplying canonical defaults.
        args: `argparse.Namespace`. Parsed positional values and optional overrides.

    Returns:
        CompletionMetadata: Fully resolved metadata for the completion log.

    Raises:
        ValueError: Raised when positional values match neither supported contract.
    """
    details = [str(value).strip() for value in args.details]
    if len(details) == 2:
        change_type, summary = details
        legacy_domain = task.domain
        legacy_title = task.title
        legacy_why = task.description
        legacy_impact = summary
    elif len(details) == 6:
        legacy_domain, legacy_title, change_type, legacy_why, summary, legacy_impact = details
    else:
        raise ValueError(
            "complete-work expects CHANGE_TYPE SUMMARY, or the legacy "
            "DOMAIN TITLE CHANGE_TYPE WHY DESCRIPTION IMPACT form.",
        )

    domain = str(args.domain or legacy_domain).strip()
    title = str(args.title or legacy_title).strip()
    why = str(args.why if args.why is not None else legacy_why).strip()
    impact = str(args.impact if args.impact is not None else legacy_impact).strip()
    if not change_type or not summary:
        raise ValueError("Change type and completion summary must not be empty.")
    if not domain or not title:
        raise ValueError("Resolved log domain and title must not be empty.")
    return CompletionMetadata(
        domain=domain,
        title=title,
        change_type=change_type,
        why=why,
        description=summary,
        impact=impact,
    )


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

