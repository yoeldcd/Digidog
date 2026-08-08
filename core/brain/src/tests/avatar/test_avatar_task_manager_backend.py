"""Workspace-isolation tests for the task-manager backend."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from brain.application.backlog.contracts import AttachmentPersistenceError
from brain.application.backlog.contracts import AttachmentValidationError
from brain.application.backlog.contracts import CreateTaskRequest
from brain.application.backlog.contracts import EditTaskRequest
from brain.application.backlog.service import list_backlog_tasks
from brain.application.backlog.service import remove_backlog_task
from brain.application.backlog.task_manager import TaskManagerService
from brain.infrastructure.backlog import CanonicalPngAttachmentStore
from brain.infrastructure.backlog import JsonRegisteredProjectCatalog


PNG = b"\x89PNG\r\n\x1a\ncontentIEND\xaeB`\x82"
PNG_UPDATED = b"\x89PNG\r\n\x1a\nupdatedIEND\xaeB`\x82"


def _components(
    tmp_path: Path,
) -> tuple[
    TaskManagerService,
    JsonRegisteredProjectCatalog,
    Path,
    Path,
]:
    """Create two registered temporary consumers and their service."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    registry = tmp_path / "brain_mirrors.json"
    registry.write_text(
        json.dumps(
            [
                {"name": "First", "path": str(first)},
                {"name": "Second", "path": str(second)},
            ],
        ),
        encoding="utf-8",
    )
    catalog = JsonRegisteredProjectCatalog(registry)
    manager = TaskManagerService(catalog, CanonicalPngAttachmentStore())
    return manager, catalog, first, second


def test_two_registered_workspaces_are_isolated(tmp_path: Path) -> None:
    """Tasks and pictures remain owned by their selected consumer."""
    manager, _, first, second = _components(tmp_path)
    first_result = manager.create_task(
        CreateTaskRequest(
            first,
            "ui.avatar",
            "First task",
            "One",
            "HIGH",
            PNG,
        ),
    )
    second_result = manager.create_task(
        CreateTaskRequest(second, "api", "Second task", "Two"),
    )

    assert [project.name for project in manager.list_projects()] == [
        "First",
        "Second",
    ]
    assert [task.title for task in manager.list_tasks(first)] == ["First task"]
    assert [task.title for task in manager.list_tasks(second)] == ["Second task"]
    expected_picture = first / "$agent" / "pictures" / "backlog-pic-t1.png"
    assert first_result.attachment_path == expected_picture
    assert first_result.attachment_path.read_bytes() == PNG
    assert second_result.attachment_path is None
    assert not (second / "$agent" / "pictures").exists()


def test_reused_task_id_without_capture_discards_stale_picture(
    tmp_path: Path,
) -> None:
    """A no-capture task cannot inherit a deleted task's picture."""
    manager, _, first, _ = _components(tmp_path)
    original = manager.create_task(
        CreateTaskRequest(first, "ui", "Original", "Original", annotated_png=PNG),
    )
    remove_backlog_task(first, original.task.task_id, force=True)

    replacement = manager.create_task(
        CreateTaskRequest(first, "ui", "Replacement", "Replacement"),
    )

    assert replacement.task.task_id == original.task.task_id
    assert replacement.attachment_path is None
    assert not (first / "$agent" / "pictures" / "backlog-pic-t1.png").exists()


def test_reused_task_id_with_capture_replaces_stale_picture(tmp_path: Path) -> None:
    """A captured replacement owns fresh bytes for its reused task ID."""
    manager, _, first, _ = _components(tmp_path)
    original = manager.create_task(
        CreateTaskRequest(first, "ui", "Original", "Original", annotated_png=PNG),
    )
    remove_backlog_task(first, original.task.task_id, force=True)

    replacement = manager.create_task(
        CreateTaskRequest(
            first,
            "ui",
            "Replacement",
            "Replacement",
            annotated_png=PNG_UPDATED,
        ),
    )

    assert replacement.task.task_id == original.task.task_id
    assert replacement.attachment_path is not None
    assert replacement.attachment_path.read_bytes() == PNG_UPDATED


def test_status_filter_is_local_and_explicit(tmp_path: Path) -> None:
    """Status filters apply only after resolving the selected project."""
    manager, _, first, _ = _components(tmp_path)
    manager.create_task(CreateTaskRequest(first, "ui", "Pending", "Pending"))

    pending = manager.list_tasks(first, frozenset({"TODO"}))
    assert [task.title for task in pending] == ["Pending"]
    assert manager.list_tasks(first, frozenset({"DONE"})) == ()


def test_invalid_png_fails_before_task_creation(tmp_path: Path) -> None:
    """Attachment validation cannot leave an orphan task or picture."""
    manager, _, first, _ = _components(tmp_path)

    with pytest.raises(AttachmentValidationError, match="complete PNG"):
        manager.create_task(
            CreateTaskRequest(
                first,
                "ui",
                "Invalid",
                "Invalid",
                annotated_png=b"bad",
            ),
        )

    assert list_backlog_tasks(first, show_all=True) == []
    assert not (first / "$agent" / "pictures").exists()


def test_attachment_path_rejects_a_picture_root_escape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A resolved pictures link cannot redirect attachments outside the consumer."""
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    pictures = workspace / "$agent" / "pictures"
    real_resolve = Path.resolve

    def resolve_with_escape(path: Path, strict: bool = False) -> Path:
        """Simulate a stale junction resolving the pictures directory outside."""
        if path == pictures:
            return outside
        return real_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve_with_escape)
    with pytest.raises(AttachmentPersistenceError, match="escapes"):
        CanonicalPngAttachmentStore().save(workspace, "t1", PNG)
    assert not (outside / "backlog-pic-t1.png").exists()


def test_attachment_failure_rolls_back_task(tmp_path: Path) -> None:
    """A failed post-ID image write removes the just-created task."""
    seeded_manager, catalog, first, _ = _components(tmp_path)
    original = seeded_manager.create_task(
        CreateTaskRequest(first, "ui", "Original", "Original", annotated_png=PNG),
    )
    stale_picture = original.attachment_path
    assert stale_picture is not None
    remove_backlog_task(first, original.task.task_id, force=True)

    class FailingStore(CanonicalPngAttachmentStore):
        """Test adapter that simulates a durable write failure."""

        def save(
            self,
            workspace_root: Path,
            task_id: str,
            content: bytes,
        ) -> Path:
            """Fail after the application has allocated the task ID."""
            raise AttachmentPersistenceError(
                "The task attachment could not be persisted.",
            )

    manager = TaskManagerService(catalog, FailingStore())
    with pytest.raises(AttachmentPersistenceError):
        manager.create_task(
            CreateTaskRequest(
                first,
                "ui",
                "Rollback",
                "Rollback",
                annotated_png=PNG,
            ),
        )

    assert list_backlog_tasks(first, show_all=True) == []
    assert not stale_picture.exists()


def test_captured_task_injects_reference_marker_once(tmp_path: Path) -> None:
    """Captured creation persists exactly one canonical reference marker."""
    manager, _, first, _ = _components(tmp_path)

    created = manager.create_task(
        CreateTaskRequest(
            first,
            "ui",
            "Captured",
            "Evidence\n\n{ref_image}",
            annotated_png=PNG,
        ),
    )

    assert created.task.description.count("{ref_image}") == 1


def test_edit_attachment_failure_restores_raw_task_and_previous_png(tmp_path: Path) -> None:
    """Replacement failure restores both prior task fields and attachment bytes."""
    seeded_manager, catalog, first, _ = _components(tmp_path)
    original = seeded_manager.create_task(
        CreateTaskRequest(first, "ui", "Original", "Original", annotated_png=PNG),
    )
    attachment_path = original.attachment_path
    assert attachment_path is not None

    class FailOnceStore(CanonicalPngAttachmentStore):
        """Fail the replacement write while allowing rollback restoration."""

        def __init__(self) -> None:
            """Initialize one pending simulated failure."""
            self._should_fail = True

        def save(self, workspace_root: Path, task_id: str, content: bytes) -> Path:
            """Fail once, then delegate restoration to the canonical adapter."""
            if self._should_fail:
                self._should_fail = False
                raise AttachmentPersistenceError("Simulated replacement failure.")

            return super().save(workspace_root, task_id, content)

    manager = TaskManagerService(catalog, FailOnceStore())
    with pytest.raises(AttachmentPersistenceError, match="replacement failure"):
        manager.edit_task(
            EditTaskRequest(
                workspace_root=first,
                task_id=original.task.task_id,
                title="Changed",
                description="Changed",
                annotated_png=PNG_UPDATED,
            ),
        )

    restored = manager.list_tasks(first)[0]
    assert restored.title == "Original"
    assert restored.description == "Original\n\n{ref_image}"
    assert attachment_path.read_bytes() == PNG

def test_unregistered_workspace_is_rejected(tmp_path: Path) -> None:
    """An arbitrary existing directory cannot become the active consumer."""
    manager, _, _, _ = _components(tmp_path)
    outsider = tmp_path / "outsider"
    outsider.mkdir()

    with pytest.raises(ValueError, match="not a registered consumer"):
        manager.list_tasks(outsider)