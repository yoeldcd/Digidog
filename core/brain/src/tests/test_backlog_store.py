# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Regression tests for the SQLite-backed task backlog."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from brain.application.backlog.service import (
    BacklogTaskDeletionError,
    create_backlog_task,
    list_backlog_tasks,
    migrate_legacy_backlog,
    remove_backlog_task,
    set_backlog_task_status,
)


class BacklogStoreTests(unittest.TestCase):
    """Verify legacy migration and durable task state transitions."""

    def _write_legacy_backlog(self, workspace_root: Path) -> None:
        source = workspace_root / "$agent" / "data" / "backlog.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            "# brain\n"
            "## explorer\n"
            "- [ ] #t3 (HIGH): Migrate the explorer - Use the logs database\n"
            "- [x] #t7 (LOW): Preserve compatibility - Keep old task-finished (checked: 01-07-2026 10:30 am)\n",
            encoding="utf-8",
        )

    def test_legacy_backlog_migrates_once_without_overwriting_database_state(self) -> None:
        """Legacy Markdown import inserts missing IDs and preserves DB ownership after that."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            self._write_legacy_backlog(workspace_root)

            first = migrate_legacy_backlog(workspace_root)
            self.assertEqual(first.imported, 2)
            self.assertEqual(first.existing, 0)
            self.assertEqual(
                [task.task_id for task in list_backlog_tasks(workspace_root, show_all=True)],
                ["t3", "t7"],
            )

            set_backlog_task_status(workspace_root, "t3", "DONE")
            legacy_path = workspace_root / "$agent" / "data" / "backlog.md"
            legacy_path.write_text(
                legacy_path.read_text(encoding="utf-8").replace("Migrate the explorer", "Legacy overwrite attempt"),
                encoding="utf-8",
            )

            second = migrate_legacy_backlog(workspace_root)
            tasks = {task.task_id: task for task in list_backlog_tasks(workspace_root, show_all=True)}
            self.assertEqual(second.imported, 0)
            self.assertEqual(second.existing, 2)
            self.assertEqual(tasks["t3"].status, "DONE")
            self.assertEqual(tasks["t3"].title, "Migrate the explorer")

    def test_status_transitions_and_deletion_guard_are_persisted(self) -> None:
        """Unfinished tasks require force deletion, while DONE tasks delete normally."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            task = create_backlog_task(workspace_root, "brain.explorer", "Persist status", "Store state in SQLite", "MEDIUM")
            self.assertEqual(task.task_id, "t1")
            self.assertEqual(task.status, "TODO")

            with self.assertRaises(BacklogTaskDeletionError):
                remove_backlog_task(workspace_root, task.task_id)

            done_task = set_backlog_task_status(workspace_root, task.task_id, "DONE")
            self.assertTrue(done_task.completed_at)
            remove_backlog_task(workspace_root, task.task_id)
            self.assertEqual(list_backlog_tasks(workspace_root), [])

            forced = create_backlog_task(workspace_root, "brain.explorer", "Force delete", "Only with intent", "LOW")
            remove_backlog_task(workspace_root, forced.task_id, force=True)
            self.assertEqual(list_backlog_tasks(workspace_root), [])

    def test_new_task_id_continues_after_migrated_legacy_ids(self) -> None:
        """New IDs remain stable after a legacy source contributes higher numbers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            self._write_legacy_backlog(workspace_root)
            migrate_legacy_backlog(workspace_root)

            task = create_backlog_task(workspace_root, "brain", "Next task", "No collision", "HIGH")
            self.assertEqual(task.task_id, "t8")


if __name__ == "__main__":
    unittest.main()
