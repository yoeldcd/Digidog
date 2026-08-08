"""Canonical PNG attachment adapter for task management."""

from __future__ import annotations

import re
from pathlib import Path

from brain.application.backlog.contracts import AttachmentPersistenceError
from brain.application.backlog.contracts import AttachmentValidationError


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_END = b"IEND\xaeB`\x82"
TASK_ID_PATTERN = re.compile(r"^t\d+$")


class CanonicalPngAttachmentStore:
    """Persist validated PNG bytes under an explicit consumer root."""

    def validate(self, content: bytes) -> None:
        """Reject non-PNG or structurally incomplete byte strings."""
        is_complete_png = (
            isinstance(content, bytes)
            and content.startswith(PNG_SIGNATURE)
            and content.endswith(PNG_END)
        )
        if not is_complete_png:
            raise AttachmentValidationError(
                "Task attachment must be a complete PNG image.",
            )

    def discard(self, workspace_root: Path, task_id: str) -> None:
        """Remove any canonical PNG left by an earlier use of a task ID."""
        target = _attachment_path(workspace_root, task_id)
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            raise AttachmentPersistenceError(
                "The stale task attachment could not be removed.",
            ) from exc

    def save(self, workspace_root: Path, task_id: str, content: bytes) -> Path:
        """Atomically persist PNG bytes after a canonical task ID exists."""
        self.validate(content)
        if TASK_ID_PATTERN.fullmatch(task_id) is None:
            raise AttachmentValidationError(
                "Task attachment requires a canonical task ID.",
            )
        target = _attachment_path(workspace_root, task_id)
        pictures_dir = target.parent
        pending = pictures_dir / f".{target.name}.pending"
        try:
            pictures_dir.mkdir(parents=True, exist_ok=True)
            pending.write_bytes(content)
            pending.replace(target)
        except OSError as exc:
            _discard_pending(pending)
            raise AttachmentPersistenceError(
                "The task attachment could not be persisted.",
            ) from exc
        return target


def _discard_pending(path: Path) -> None:
    """Best-effort cleanup for an interrupted atomic attachment write."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass

def _attachment_path(workspace_root: Path, task_id: str) -> Path:
    """Return a contained canonical PNG path for one explicit workspace and task ID."""
    if TASK_ID_PATTERN.fullmatch(task_id) is None:
        raise AttachmentValidationError(
            "Task attachment requires a canonical task ID.",
        )
    resolved_workspace = workspace_root.resolve()
    pictures_dir = resolved_workspace / "$agent" / "pictures"
    try:
        pictures_dir.resolve().relative_to(resolved_workspace)
    except ValueError as exc:
        raise AttachmentPersistenceError(
            "The task attachment directory escapes the selected workspace.",
        ) from exc
    return pictures_dir / f"backlog-pic-{task_id}.png"