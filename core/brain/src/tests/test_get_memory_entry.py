"""Regression tests for memory entry command routing."""

from __future__ import annotations

import argparse
import json

from brain.presentation.actions.memory import command_get_memory_entry


def _args(domain: str, key: str | None = None) -> argparse.Namespace:
    """Build the minimal command namespace used by retrieval tests."""
    return argparse.Namespace(
        color=False,
        domain=domain,
        full_text=False,
        json=True,
        json_envelope=False,
        key=key,
        limit=None,
        uptime_order=False,
        verbose_log=False,
    )


def test_global_index_is_readable_as_index_entry(tmp_path, monkeypatch, capsys) -> None:
    """Resolve bare `index` to the Markdown file at the memory root."""
    memory_root = tmp_path / "memory"
    memory_root.mkdir()
    expected_content = "# Global memory index\n"
    (memory_root / "index.md").write_text(expected_content, encoding="utf-8")
    monkeypatch.setattr(command_get_memory_entry.memory_paths, "MEMORY_ROOT", memory_root)

    exit_code = command_get_memory_entry.handle(_args(domain="index"))

    assert exit_code == 0
    assert capsys.readouterr().out == f"<RAW DOCUMENT>\n{expected_content}"


def test_domain_index_routing_remains_unchanged(tmp_path, monkeypatch, capsys) -> None:
    """Keep existing `domain.index` retrieval behavior intact."""
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
    tmp_path, monkeypatch, capsys
) -> None:
    """Return terminal Markdown verbatim instead of JSON-escaped text."""
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
    tmp_path, monkeypatch, capsys
) -> None:
    """Preserve the structured payload explicitly requested by Explorer."""
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
    tmp_path, monkeypatch, capsys
) -> None:
    """Keep directory indexes machine-readable while terminal files stay raw."""
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
