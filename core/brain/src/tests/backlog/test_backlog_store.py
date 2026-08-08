# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Regression tests for the SQLite-backed task backlog."""

from __future__ import annotations

import os
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
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_root = Path(tmp_dir).resolve()
            self._write_legacy_backlog(workspace_root)

            first_report = migrate_legacy_backlog(workspace_root)
            self.assertEqual(first_report.imported, 2)
            self.assertEqual(first_report.existing, 0)

            second_report = migrate_legacy_backlog(workspace_root)
            self.assertEqual(second_report.imported, 0)
            self.assertEqual(second_report.existing, 2)

            tasks = list_backlog_tasks(workspace_root, show_all=True)
            self.assertEqual(len(tasks), 2)
            by_id = {task.task_id: task for task in tasks}

            self.assertEqual(by_id["t3"].status, "TODO")
            self.assertEqual(by_id["t7"].status, "DONE")
            self.assertEqual(by_id["t7"].completed_at, "01-07-2026 10:30 am")

            set_backlog_task_status(workspace_root, "t3", "WORKING")
            third_report = migrate_legacy_backlog(workspace_root)
            self.assertEqual(third_report.imported, 0)
            self.assertEqual(third_report.existing, 2)

            reloaded_tasks = list_backlog_tasks(workspace_root, show_all=True)
            reloaded_by_id = {task.task_id: task for task in reloaded_tasks}
            self.assertEqual(reloaded_by_id["t3"].status, "WORKING")

    def test_new_task_id_continues_after_migrated_legacy_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_root = Path(tmp_dir).resolve()
            self._write_legacy_backlog(workspace_root)

            created_task = create_backlog_task(
                workspace_root=workspace_root,
                domain="core.brain.test",
                title="Follow-up task",
                description="Should receive t8 identifier",
                priority="MEDIUM",
            )
            self.assertEqual(created_task.task_id, "t8")

            tasks = list_backlog_tasks(workspace_root, show_all=True)
            self.assertEqual(len(tasks), 3)

    def test_status_transitions_and_deletion_guard_are_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_root = Path(tmp_dir).resolve()

            task = create_backlog_task(
                workspace_root=workspace_root,
                domain="core.brain.test",
                title="State transition test",
                description="Verify deletion guards",
                priority="HIGH",
            )
            self.assertEqual(task.status, "TODO")

            with self.assertRaises(BacklogTaskDeletionError):
                remove_backlog_task(workspace_root=workspace_root, task_id=task.task_id, force=False)

            working_task = set_backlog_task_status(workspace_root, task.task_id, "WORKING")
            self.assertEqual(working_task.status, "WORKING")

            done_task = set_backlog_task_status(workspace_root, task.task_id, "DONE")
            self.assertEqual(done_task.status, "DONE")
            self.assertNotEqual(done_task.completed_at, "")

            remove_backlog_task(workspace_root=workspace_root, task_id=task.task_id, force=False)
            self.assertEqual(len(list_backlog_tasks(workspace_root, show_all=True)), 0)

    def test_read_task_action_handler_with_json_and_text(self) -> None:
        """Verify read-task action handler with positional ID and --id flag."""
        from brain.presentation.actions.backlog.command_read_task import handle as handle_read_task

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_root = Path(tmp_dir).resolve()
            old_env = os.environ.get("WORKSPACE_ROOT")
            os.environ["WORKSPACE_ROOT"] = str(workspace_root)
            try:
                task = create_backlog_task(
                    workspace_root=workspace_root,
                    domain="core.brain.cli",
                    title="Test read-task feature",
                    description="Detailed description for testing read-task.",
                    priority="HIGH",
                )

                class DummyArgs:
                    task_id = task.task_id
                    id = ""
                    json = True
                    color = False

                args = DummyArgs()
                status = handle_read_task(args)  # type: ignore[arg-type]
                self.assertEqual(status, 0)
                payload = getattr(args, "json_payload", {})
                self.assertTrue(payload.get("ok"))
                self.assertEqual(payload["task"]["id"], task.task_id)
                self.assertEqual(payload["task"]["title"], "Test read-task feature")

                # Test via --id flag with numeric ID
                class DummyArgsFlag:
                    task_id = ""
                    id = task.task_id.replace("t", "")
                    json = False
                    color = False

                args_flag = DummyArgsFlag()
                status_flag = handle_read_task(args_flag)  # type: ignore[arg-type]
                self.assertEqual(status_flag, 0)
            finally:
                if old_env is not None:
                    os.environ["WORKSPACE_ROOT"] = old_env
                else:
                    os.environ.pop("WORKSPACE_ROOT", None)

    def test_read_task_action_handler_not_found(self) -> None:
        """Verify read-task error handling for non-existent task IDs."""
        from brain.presentation.actions.backlog.command_read_task import handle as handle_read_task

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace_root = Path(tmp_dir).resolve()
            old_env = os.environ.get("WORKSPACE_ROOT")
            os.environ["WORKSPACE_ROOT"] = str(workspace_root)
            try:
                class DummyArgs:
                    task_id = "t99999"
                    id = ""
                    json = True
                    color = False

                args = DummyArgs()
                status = handle_read_task(args)  # type: ignore[arg-type]
                self.assertEqual(status, 1)
                payload = getattr(args, "json_payload", {})
                self.assertFalse(payload.get("ok"))
            finally:
                if old_env is not None:
                    os.environ["WORKSPACE_ROOT"] = old_env
                else:
                    os.environ.pop("WORKSPACE_ROOT", None)
