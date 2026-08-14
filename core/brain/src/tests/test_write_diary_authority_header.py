"""Regression coverage for root authorization on written diary files."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from brain.presentation.actions.diary import command_write_diary


ROOT_AUTHORIZATION_HEADER: str = "<!-- Authorized: root -->"


def _args(timestamp: str, title: str, text: str) -> argparse.Namespace:
    """Build the minimal namespace required by the write-diary action.

    Args:
        timestamp: Diary entry timestamp in the command's accepted format.
        title: Diary entry title.
        text: Diary entry body.

    Returns:
        argparse.Namespace: Parsed-command substitute for the focused tests.
    """

    return argparse.Namespace(
        body=None,
        color=False,
        datetime=timestamp,
        text=text,
        title=title,
    )


def _install_temp_storage(monkeypatch: pytest.MonkeyPatch, diary_path: Path) -> None:
    """Route diary reads and writes to one isolated temporary path.

    Args:
        monkeypatch: Pytest patcher for replacing command storage boundaries.
        diary_path: Temporary diary file used by the test.

    Returns:
        None: The monkeypatch fixture is configured in place.
    """

    def resolve_temp_path(_category: str, _key: str) -> Path:
        """Return the isolated diary path for every command lookup.

        Args:
            _category: Diary category supplied by the command under test.
            _key: Diary key supplied by the command under test.

        Returns:
            Path: Isolated diary path used for the command lookup.
        """

        return diary_path

    def write_temp_instance(_category: str, _key: str, content: str) -> Path:
        """Persist command output only inside the pytest temporary directory.

        Args:
            _category: Diary category supplied by the command under test.
            _key: Diary key supplied by the command under test.
            content: Diary Markdown content produced by the command.

        Returns:
            Path: Isolated diary path receiving the persisted content.
        """

        diary_path.parent.mkdir(parents=True, exist_ok=True)
        diary_path.write_text(content, encoding="utf-8")

        return diary_path

    def disable_log_step(*_args: object, **_kwargs: object) -> None:
        """Suppress progress output while testing persisted content.

        Args:
            _args: Positional progress arguments ignored by the test helper.
            _kwargs: Keyword progress arguments ignored by the test helper.

        Returns:
            None: Progress output is intentionally suppressed.
        """

        return None

    monkeypatch.setattr(command_write_diary, "resolve_file_path", resolve_temp_path)
    monkeypatch.setattr(command_write_diary, "write_instance", write_temp_instance)
    monkeypatch.setattr(command_write_diary, "log_step", disable_log_step)


def test_new_diary_file_has_root_authorization_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prefix a new daily diary file with one root authorization header.

    Args:
        tmp_path: Isolated pytest directory for the diary file.
        monkeypatch: Pytest patcher for replacing command storage boundaries.

    Returns:
        None: The test passes when new content has the required prefix once.
    """

    diary_path = tmp_path / "2026-08" / "14-08-2026.md"
    _install_temp_storage(monkeypatch, diary_path)

    exit_code = command_write_diary.handle(
        _args("14-08-2026 09:30:00", "Morning", "Started the workday.")
    )

    content = diary_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert content.startswith(
        f"{ROOT_AUTHORIZATION_HEADER}\n\n# Diary - 14-08-2026\n\n"
    )
    assert content.count(ROOT_AUTHORIZATION_HEADER) == 1


def test_diary_update_retains_one_root_authorization_header_and_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep one root header while rebuilding entries in chronological order.

    Args:
        tmp_path: Isolated pytest directory for the diary file.
        monkeypatch: Pytest patcher for replacing command storage boundaries.

    Returns:
        None: The test passes when updates retain one header and sorted entries.
    """

    diary_path = tmp_path / "2026-08" / "14-08-2026.md"
    _install_temp_storage(monkeypatch, diary_path)

    first_exit_code = command_write_diary.handle(
        _args("14-08-2026 09:30:00", "Morning", "Started the workday.")
    )
    second_exit_code = command_write_diary.handle(
        _args("14-08-2026 10:15:00", "Checkpoint", "Recorded the checkpoint.")
    )

    content = diary_path.read_text(encoding="utf-8")
    first_entry = "## 14-08-2026 09:30:00 - Morning"
    second_entry = "## 14-08-2026 10:15:00 - Checkpoint"
    assert first_exit_code == 0
    assert second_exit_code == 0
    assert content.count(ROOT_AUTHORIZATION_HEADER) == 1
    assert content.index(first_entry) < content.index(second_entry)
    assert "Started the workday." in content
    assert "Recorded the checkpoint." in content


def test_legacy_diary_update_adds_one_root_authorization_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Add one root header while preserving legacy diary content and order.

    Args:
        tmp_path: Isolated pytest directory for the diary file.
        monkeypatch: Pytest patcher for replacing command storage boundaries.

    Returns:
        None: The test passes when legacy content receives one required prefix.
    """

    diary_path = tmp_path / "2026-08" / "14-08-2026.md"
    diary_path.parent.mkdir(parents=True)
    diary_path.write_text(
        "# Diary - 14-08-2026\n\n"
        "## 14-08-2026 08:00:00 - Legacy\n\n"
        "Existing legacy entry.\n",
        encoding="utf-8",
    )
    _install_temp_storage(monkeypatch, diary_path)

    exit_code = command_write_diary.handle(
        _args("14-08-2026 11:00:00", "New", "Added after the legacy entry.")
    )

    content = diary_path.read_text(encoding="utf-8")
    legacy_entry = "## 14-08-2026 08:00:00 - Legacy"
    new_entry = "## 14-08-2026 11:00:00 - New"
    assert exit_code == 0
    assert content.startswith(f"{ROOT_AUTHORIZATION_HEADER}\n\n# Diary - 14-08-2026\n\n")
    assert content.count(ROOT_AUTHORIZATION_HEADER) == 1
    assert content.index(legacy_entry) < content.index(new_entry)
    assert "Existing legacy entry." in content
    assert "Added after the legacy entry." in content
