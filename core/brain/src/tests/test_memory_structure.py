"""Regression tests for authority-filtered memory structure projections."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from brain.application.memory import paths as memory_paths
from brain.presentation.actions.memory import command_memory_structure


def _file_node() -> dict[str, object]:
    """Return representative source metadata for an indexed Markdown file.

    Args:
        None.

    Returns:
        dict[str, object]: Fresh file-node metadata for one test tree.
    """

    return {
        "__type__": "file",
        "mtime": 0.0,
        "size": "1.0KB",
        "lines": "10",
        "entries": 3,
    }


def _tree_with_indexes() -> dict[str, object]:
    """Build a tree containing root and domain index nodes.

    Args:
        None.

    Returns:
        dict[str, object]: Fresh index tree for root and nested index tests.
    """
    profiles_node = {
        "__type__": "dir",
        "mtime": 0.0,
        "entries": 1,
        "children": {
            "index": _file_node(),
        },
    }

    return {
        "profiles": profiles_node,
        "index": _file_node(),
    }


def _mixed_tree() -> dict[str, object]:
    """Build a tree containing visible, restricted, and empty branches.

    Args:
        None.

    Returns:
        dict[str, object]: Fresh mixed-authority index tree.
    """
    nested_node = {
        "__type__": "dir",
        "mtime": 0.0,
        "entries": 2,
        "children": {
            "nested_hidden": _file_node(),
            "nested_public": _file_node(),
        },
    }
    alpha_node = {
        "__type__": "dir",
        "mtime": 0.0,
        "entries": 3,
        "children": {
            "hidden": _file_node(),
            "nested": nested_node,
            "visible": _file_node(),
        },
    }
    empty_node = {
        "__type__": "dir",
        "mtime": 0.0,
        "entries": 1,
        "children": {
            "secret": _file_node(),
        },
    }

    return {
        "alpha": alpha_node,
        "empty": empty_node,
        "public": _file_node(),
    }


def _write_memory_file(memory_root: Path, dotted_path: str, content: str) -> Path:
    """Write one temporary Markdown document using a dotted memory path.

    Args:
        memory_root: Temporary root substituted for the managed memory directory.
        dotted_path: Dotted directory and file-stem path from an index node.
        content: Raw Markdown content used by the authority guard.

    Returns:
        Path: Absolute temporary Markdown path written for the test.
    """
    parts = tuple(dotted_path.split("."))
    file_path = memory_root.joinpath(*parts[:-1], f"{parts[-1]}.md")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")

    return file_path


def _args(
    json_output: bool,
    color: bool = False,
    limit: int | None = None,
    authority: str = "orchestrator",
) -> argparse.Namespace:
    """Build memory-structure command arguments for one invocation.

    Args:
        json_output: Whether the command should emit its JSON path schema.
        color: Whether terminal placeholders should be rendered with color.
        limit: Optional per-level output limit.
        authority: Caller authority passed to the command.

    Returns:
        argparse.Namespace: Parsed-style arguments accepted by the command.
    """
    args = argparse.Namespace(
        color=color,
        json=json_output,
        limit=limit,
        uptime_order=False,
        verbose_log=False,
        authority=authority,
    )

    return args


def test_json_structure_includes_root_and_domain_indexes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Expose authorized root and domain index nodes in JSON output.

    Args:
        tmp_path: Temporary managed memory root for canonical path resolution.
        capsys: Pytest output capture fixture used to inspect JSON output.

    Returns:
        None.
    """
    tree = _tree_with_indexes()
    _write_memory_file(tmp_path, "index", "# Root index\n")
    _write_memory_file(tmp_path, "profiles.index", "# Profiles index\n")

    with (
        patch.object(command_memory_structure, "load_index", return_value=tree) as load_index,
        patch.object(memory_paths, "MEMORY_ROOT", tmp_path),
    ):
        exit_code = command_memory_structure.handle(_args(json_output=True))

    paths = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert paths == ["profiles", "profiles.index", "index"]
    load_index.assert_called_once_with(include_indexes=True)


def test_terminal_structure_includes_root_and_domain_indexes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Expose authorized index nodes in the terminal tree.

    Args:
        tmp_path: Temporary managed memory root for canonical path resolution.
        capsys: Pytest output capture fixture used to inspect terminal output.

    Returns:
        None.
    """
    tree = _tree_with_indexes()
    _write_memory_file(tmp_path, "index", "# Root index\n")
    _write_memory_file(tmp_path, "profiles.index", "# Profiles index\n")

    with (
        patch.object(command_memory_structure, "load_index", return_value=tree) as load_index,
        patch.object(memory_paths, "MEMORY_ROOT", tmp_path),
    ):
        exit_code = command_memory_structure.handle(_args(json_output=False, color=True))

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "index" in output
    assert "profiles/" in output
    load_index.assert_called_once_with(include_indexes=True)


def test_json_projection_removes_hidden_branches_and_recomputes_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Filter restricted files, remove empty directories, and preserve raw input.

    Args:
        tmp_path: Temporary managed memory root for canonical path resolution.
        capsys: Pytest output capture fixture used to inspect JSON output.

    Returns:
        None.
    """
    tree = _mixed_tree()
    original_tree = copy.deepcopy(tree)
    _write_memory_file(tmp_path, "alpha.hidden", "<!-- Unauthorized: worker -->\n# Hidden\n")
    _write_memory_file(
        tmp_path,
        "alpha.nested.nested_hidden",
        "<!-- Unauthorized: worker -->\n# Hidden\n",
    )
    _write_memory_file(tmp_path, "alpha.nested.nested_public", "# Public\n")
    _write_memory_file(tmp_path, "alpha.visible", "# Visible\n")
    _write_memory_file(tmp_path, "empty.secret", "<!-- Unauthorized: worker -->\n# Hidden\n")
    _write_memory_file(tmp_path, "public", "# Public\n")

    with (
        patch.object(command_memory_structure, "load_index", return_value=tree),
        patch.object(memory_paths, "MEMORY_ROOT", tmp_path),
    ):
        exit_code = command_memory_structure.handle(
            _args(json_output=True, authority="worker"),
        )

    paths = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert paths == [
        "alpha",
        "alpha.nested",
        "alpha.nested.nested_public",
        "alpha.visible",
        "public",
    ]
    assert tree == original_tree


def test_terminal_projection_hides_names_and_recomputes_visible_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Render only visible nodes and never expose hidden source counts.

    Args:
        tmp_path: Temporary managed memory root for canonical path resolution.
        capsys: Pytest output capture fixture used to inspect terminal output.

    Returns:
        None.
    """
    tree = _mixed_tree()
    _write_memory_file(tmp_path, "alpha.hidden", "<!-- Unauthorized: worker -->\n# Hidden\n")
    _write_memory_file(
        tmp_path,
        "alpha.nested.nested_hidden",
        "<!-- Unauthorized: worker -->\n# Hidden\n",
    )
    _write_memory_file(tmp_path, "alpha.nested.nested_public", "# Public\n")
    _write_memory_file(tmp_path, "alpha.visible", "# Visible\n")
    _write_memory_file(tmp_path, "empty.secret", "<!-- Unauthorized: worker -->\n# Hidden\n")
    _write_memory_file(tmp_path, "public", "# Public\n")

    with (
        patch.object(command_memory_structure, "load_index", return_value=tree),
        patch.object(memory_paths, "MEMORY_ROOT", tmp_path),
    ):
        exit_code = command_memory_structure.handle(
            _args(json_output=False, authority="worker"),
        )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "alpha/" in output
    assert "(E: 2)" in output
    assert "nested/" in output
    assert "(E: 1)" in output
    assert "nested_public" in output
    assert "visible" in output
    assert "public" in output
    assert "empty/" not in output
    assert "hidden" not in output
    assert "secret" not in output
    assert "(E: 3)" not in output


def test_limit_is_applied_after_authority_filtering(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep visible entries from being displaced by hidden earlier entries.

    Args:
        tmp_path: Temporary managed memory root for canonical path resolution.
        capsys: Pytest output capture fixture used to inspect JSON output.

    Returns:
        None.
    """
    tree = {
        "a_hidden": _file_node(),
        "z_public": _file_node(),
    }
    _write_memory_file(tmp_path, "a_hidden", "<!-- Unauthorized: worker -->\n# Hidden\n")
    _write_memory_file(tmp_path, "z_public", "# Public\n")

    with (
        patch.object(command_memory_structure, "load_index", return_value=tree),
        patch.object(memory_paths, "MEMORY_ROOT", tmp_path),
    ):
        exit_code = command_memory_structure.handle(
            _args(json_output=True, limit=1, authority="worker"),
        )

    paths = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert paths == ["z_public"]


def test_invalid_path_component_is_hidden_without_guard_access(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reject traversal-like index names before reading or guarding a file.

    Args:
        tmp_path: Temporary managed memory root for canonical path resolution.
        capsys: Pytest output capture fixture used to inspect JSON output.

    Returns:
        None.
    """
    tree = {
        "bad/name": _file_node(),
    }

    with (
        patch.object(command_memory_structure, "load_index", return_value=tree),
        patch.object(memory_paths, "MEMORY_ROOT", tmp_path),
        patch.object(command_memory_structure, "is_memory_access_allowed") as guard,
    ):
        exit_code = command_memory_structure.handle(_args(json_output=True))

    paths = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert paths == []
    guard.assert_not_called()


def test_missing_authority_fails_closed_without_privileged_fallback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reject an invocation that does not expose a caller authority.

    Args:
        tmp_path: Temporary managed memory root for canonical path resolution.
        capsys: Pytest output capture fixture used to inspect the error output.

    Returns:
        None.
    """
    tree = {
        "restricted": _file_node(),
    }
    _write_memory_file(tmp_path, "restricted", "<!-- Unauthorized: worker -->\n# Entry\n")

    with (
        patch.object(command_memory_structure, "load_index", return_value=tree) as load_index,
        patch.object(memory_paths, "MEMORY_ROOT", tmp_path),
    ):
        args = _args(json_output=True)
        del args.authority
        exit_code = command_memory_structure.handle(args)

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Command authority is required." in output
    assert "restricted" not in output
    load_index.assert_not_called()


def test_json_and_terminal_use_the_same_authority_projection(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Apply one authority projection consistently across both output modes.

    Args:
        tmp_path: Temporary managed memory root for canonical path resolution.
        capsys: Pytest output capture fixture used to inspect both output modes.

    Returns:
        None.
    """
    tree = {
        "a_hidden": _file_node(),
        "z_public": _file_node(),
    }
    _write_memory_file(tmp_path, "a_hidden", "<!-- Unauthorized: worker -->\n# Hidden\n")
    _write_memory_file(tmp_path, "z_public", "# Public\n")

    with (
        patch.object(command_memory_structure, "load_index", return_value=tree),
        patch.object(memory_paths, "MEMORY_ROOT", tmp_path),
    ):
        json_exit_code = command_memory_structure.handle(
            _args(json_output=True, authority="worker"),
        )
        json_paths = json.loads(capsys.readouterr().out)
        terminal_exit_code = command_memory_structure.handle(
            _args(json_output=False, authority="worker"),
        )
        terminal_output = capsys.readouterr().out

    assert json_exit_code == 0
    assert terminal_exit_code == 0
    assert json_paths == ["z_public"]
    assert "z_public" in terminal_output
    assert "a_hidden" not in terminal_output