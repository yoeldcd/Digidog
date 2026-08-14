"""Regression tests for memory entry command routing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from brain.presentation.actions.memory import command_get_memory_entry


def _args(
    domain: str,
    key: str | None = None,
    authority: str = "orchestrator",
) -> argparse.Namespace:
    """Build the minimal command namespace used by retrieval tests.

    Args:
        domain: Memory domain or dotted entry path under test.
        key: Optional entry key supplied separately from the domain.
        authority: Caller authority forwarded to the direct handler.

    Returns:
        argparse.Namespace: Parsed-like options used by the retrieval tests.
    """

    return argparse.Namespace(
        color=False,
        domain=domain,
        full_text=False,
        json=True,
        json_envelope=False,
        key=key,
        limit=None,
        authority=authority,
        uptime_order=False,
        verbose_log=False,
    )


def _file_node() -> dict[str, object]:
    """Build representative metadata for one indexed Markdown file.

    Args:
        None.

    Returns:
        dict[str, object]: Fresh file-node metadata used by tree projections.
    """

    return {
        "__type__": "file",
        "mtime": 0.0,
        "size": "1.0KB",
        "lines": "1",
        "entries": 0,
    }


def _write_memory_file(memory_root: Path, dotted_path: str, content: str) -> None:
    """Write one temporary Markdown document at a dotted memory path.

    Args:
        memory_root: Temporary root substituted for the managed memory directory.
        dotted_path: Dotted directory and file-stem path represented by an index node.
        content: Raw Markdown content used by the authority guard.

    Returns:
        None.
    """
    parts = dotted_path.split(".")
    file_path = memory_root.joinpath(*parts[:-1], f"{parts[-1]}.md")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def test_global_index_is_readable_as_index_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Resolve the bare index name to the Markdown file at the memory root.

    Args:
        tmp_path: Temporary root used to build an isolated memory tree.
        monkeypatch: Fixture used to redirect the configured memory root.
        capsys: Fixture used to inspect the rendered raw document.

    Returns:
        None.
    """
    memory_root = tmp_path / "memory"
    memory_root.mkdir()
    expected_content = "# Global memory index\n"
    (memory_root / "index.md").write_text(expected_content, encoding="utf-8")
    monkeypatch.setattr(command_get_memory_entry.memory_paths, "MEMORY_ROOT", memory_root)

    exit_code = command_get_memory_entry.handle(_args(domain="index"))

    assert exit_code == 0
    assert capsys.readouterr().out == f"<RAW DOCUMENT>\n{expected_content}"


def test_domain_index_routing_remains_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep existing dotted index retrieval behavior intact.

    Args:
        tmp_path: Temporary root used to build an isolated memory tree.
        monkeypatch: Fixture used to redirect the configured memory root.
        capsys: Fixture used to inspect the rendered raw document.

    Returns:
        None.
    """
    memory_root = tmp_path / "memory"
    domain_root = memory_root / "profiles"
    domain_root.mkdir(parents=True)
    expected_content = "# Profiles index\n"
    (domain_root / "index.md").write_text(expected_content, encoding="utf-8")
    monkeypatch.setattr(command_get_memory_entry.memory_paths, "MEMORY_ROOT", memory_root)

    exit_code = command_get_memory_entry.handle(_args(domain="profiles.index"))

    assert exit_code == 0
    assert capsys.readouterr().out == f"<RAW DOCUMENT>\n{expected_content}"


def test_terminal_markdown_json_mode_does_not_escape_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Return terminal Markdown verbatim instead of JSON-escaped text.

    Args:
        tmp_path: Temporary root used to build an isolated memory tree.
        monkeypatch: Fixture used to redirect the configured memory root.
        capsys: Fixture used to inspect the rendered raw document.

    Returns:
        None.
    """
    memory_root = tmp_path / "memory"
    domain_root = memory_root / "workers"
    domain_root.mkdir(parents=True)
    expected_content = "# Contract\n\n```powershell\n$VALUE = 'literal'\n```\n"
    (domain_root / "writer.md").write_text(expected_content, encoding="utf-8")
    monkeypatch.setattr(command_get_memory_entry.memory_paths, "MEMORY_ROOT", memory_root)

    exit_code = command_get_memory_entry.handle(_args(domain="workers.writer"))

    assert exit_code == 0
    assert capsys.readouterr().out == f"<RAW DOCUMENT>\n{expected_content}"


def test_terminal_markdown_can_keep_json_envelope_for_internal_consumers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Preserve the structured payload explicitly requested by Explorer.

    Args:
        tmp_path: Temporary root used to build an isolated memory tree.
        monkeypatch: Fixture used to redirect the configured memory root.
        capsys: Fixture used to inspect the structured JSON envelope.

    Returns:
        None.
    """
    memory_root = tmp_path / "memory"
    domain_root = memory_root / "workers"
    domain_root.mkdir(parents=True)
    expected_content = "# Contract\n"
    (domain_root / "writer.md").write_text(expected_content, encoding="utf-8")
    monkeypatch.setattr(command_get_memory_entry.memory_paths, "MEMORY_ROOT", memory_root)
    args = _args(domain="workers.writer")
    args.json_envelope = True

    exit_code = command_get_memory_entry.handle(args)

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "domain": "workers",
        "key": "writer",
        "content": expected_content,
    }


def test_directory_json_mode_remains_structured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep directory indexes machine-readable while terminal files stay raw.

    Args:
        tmp_path: Temporary root used to build an isolated memory tree.
        monkeypatch: Fixture used to redirect the configured memory root.
        capsys: Fixture used to inspect the structured directory payload.

    Returns:
        None.
    """
    memory_root = tmp_path / "memory"
    domain_root = memory_root / "workers"
    domain_root.mkdir(parents=True)
    (domain_root / "writer.md").write_text("# Contract\n", encoding="utf-8")
    monkeypatch.setattr(command_get_memory_entry.memory_paths, "MEMORY_ROOT", memory_root)

    exit_code = command_get_memory_entry.handle(_args(domain="workers"))

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "domain": "workers",
        "keys": ["writer"],
    }


def test_directory_json_tree_filters_restricted_files_and_empty_domains(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Hide restricted index entries, files, and branches from JSON enumeration.

    Args:
        tmp_path: Temporary root used to build an isolated memory tree.
        monkeypatch: Fixture used to redirect the memory root and indexed tree.
        capsys: Fixture used to inspect the JSON directory payload.

    Returns:
        None.
    """
    tree = {
        "workers": {
            "__type__": "dir",
            "entries": 5,
            "children": {
                "a_hidden": _file_node(),
                "empty": {
                    "__type__": "dir",
                    "entries": 1,
                    "children": {"secret": _file_node()},
                },
                "index": _file_node(),
                "nested": {
                    "__type__": "dir",
                    "entries": 2,
                    "children": {
                        "nested_hidden": _file_node(),
                        "nested_public": _file_node(),
                    },
                },
                "z_public": _file_node(),
            },
        },
    }
    _write_memory_file(tmp_path, "workers.a_hidden", "<!-- Unauthorized: worker -->\n# Hidden\n")
    _write_memory_file(tmp_path, "workers.empty.secret", "<!-- Unauthorized: worker -->\n# Secret\n")
    _write_memory_file(tmp_path, "workers.index", "<!-- Unauthorized: worker -->\n# Index\n")
    _write_memory_file(
        tmp_path,
        "workers.nested.nested_hidden",
        "<!-- Unauthorized: worker -->\n# Hidden\n",
    )
    _write_memory_file(tmp_path, "workers.nested.nested_public", "# Public\n")
    _write_memory_file(tmp_path, "workers.z_public", "# Public\n")

    monkeypatch.setattr(command_get_memory_entry.memory_paths, "MEMORY_ROOT", tmp_path)

    with patch.object(command_get_memory_entry, "load_index", return_value=tree) as load_index:
        exit_code = command_get_memory_entry.handle(_args(domain="workers", authority="worker"))

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload == {
        "ok": True,
        "domain": "workers",
        "keys": ["nested.nested_public", "z_public"],
    }
    assert "a_hidden" not in payload["keys"]
    assert "empty" not in payload["keys"]
    assert "index" not in payload["keys"]
    load_index.assert_called_once_with(include_indexes=True)


def test_directory_terminal_tree_filters_non_terminal_domains_and_recomputes_counts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Hide restricted names and use visible-only counts in terminal trees.

    Args:
        tmp_path: Temporary root used to build an isolated memory tree.
        monkeypatch: Fixture used to redirect the memory root and indexed tree.
        capsys: Fixture used to inspect the rendered terminal tree.

    Returns:
        None.
    """
    tree = {
        "workers": {
            "__type__": "dir",
            "entries": 4,
            "children": {
                "hidden": _file_node(),
                "nested": {
                    "__type__": "dir",
                    "entries": 2,
                    "children": {
                        "nested_hidden": _file_node(),
                        "nested_public": _file_node(),
                    },
                },
                "visible": _file_node(),
            },
        },
    }
    _write_memory_file(tmp_path, "workers.hidden", "<!-- Unauthorized: worker -->\n# Hidden\n")
    _write_memory_file(
        tmp_path,
        "workers.nested.nested_hidden",
        "<!-- Unauthorized: worker -->\n# Hidden\n",
    )
    _write_memory_file(tmp_path, "workers.nested.nested_public", "# Public\n")
    _write_memory_file(tmp_path, "workers.visible", "# Visible\n")

    monkeypatch.setattr(command_get_memory_entry.memory_paths, "MEMORY_ROOT", tmp_path)
    args = _args(domain="workers", authority="worker")
    args.json = False

    with patch.object(command_get_memory_entry, "load_index", return_value=tree):
        exit_code = command_get_memory_entry.handle(args)

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "workers/" in output
    assert "(E: 2)" in output
    assert "nested/" in output
    assert "(E: 1)" in output
    assert "nested_public" in output
    assert "visible" in output
    assert "hidden" not in output


def test_directory_json_limit_is_applied_after_authority_filtering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep visible entries from being displaced by restricted earlier names.

    Args:
        tmp_path: Temporary root used to build an isolated memory tree.
        monkeypatch: Fixture used to redirect the memory root and indexed tree.
        capsys: Fixture used to inspect the JSON directory payload.

    Returns:
        None.
    """
    tree = {
        "workers": {
            "__type__": "dir",
            "entries": 2,
            "children": {
                "a_hidden": _file_node(),
                "z_public": _file_node(),
            },
        },
    }
    _write_memory_file(tmp_path, "workers.a_hidden", "<!-- Unauthorized: worker -->\n# Hidden\n")
    _write_memory_file(tmp_path, "workers.z_public", "# Public\n")

    monkeypatch.setattr(command_get_memory_entry.memory_paths, "MEMORY_ROOT", tmp_path)
    args = _args(domain="workers", authority="worker")
    args.limit = 1

    with patch.object(command_get_memory_entry, "load_index", return_value=tree):
        exit_code = command_get_memory_entry.handle(args)

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "domain": "workers",
        "keys": ["z_public"],
    }


def test_full_text_json_filters_restricted_content_and_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Return only authorized entries when rendering a complete domain.

    Args:
        tmp_path: Temporary root used to build an isolated memory tree.
        monkeypatch: Fixture used to redirect the memory root.
        capsys: Fixture used to inspect the JSON full-text payload.

    Returns:
        None.
    """
    _write_memory_file(tmp_path, "workers.hidden", "<!-- Unauthorized: worker -->\nSECRET\n")
    _write_memory_file(tmp_path, "workers.visible", "PUBLIC\n")
    _write_memory_file(tmp_path, "workers.nested.hidden", "<!-- Unauthorized: worker -->\nSECRET\n")
    _write_memory_file(tmp_path, "workers.nested.visible", "NESTED PUBLIC\n")

    monkeypatch.setattr(command_get_memory_entry.memory_paths, "MEMORY_ROOT", tmp_path)
    args = _args(domain="workers", authority="worker")
    args.full_text = True

    exit_code = command_get_memory_entry.handle(args)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload == {
        "ok": True,
        "domain": "workers",
        "entries": {
            "nested.visible": "NESTED PUBLIC\n",
            "visible": "PUBLIC\n",
        },
    }


@pytest.mark.parametrize("authority", ["", None], ids=["empty", "missing"])
def test_missing_or_empty_authority_denies_before_memory_read(
    authority: str | None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reject direct handler calls before logging or reading memory.

    Args:
        authority: Empty or missing authority representation under test.
        capsys: Pytest fixture used to inspect the safe denial payload.

    Returns:
        None.
    """

    args = _args(domain="workers.writer")

    if authority is None:
        delattr(args, "authority")

    else:
        args.authority = authority

    with (
        patch.object(command_get_memory_entry, "log_step") as log_step,
        patch.object(command_get_memory_entry, "read_instance") as read_instance,
        patch.object(command_get_memory_entry, "resolve_category_dir") as resolve_category_dir,
    ):
        exit_code = command_get_memory_entry.handle(args)

    assert exit_code == 1
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "error": "Command authority is required.",
    }
    log_step.assert_not_called()
    read_instance.assert_not_called()
    resolve_category_dir.assert_not_called()
