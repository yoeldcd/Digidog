"""Regression tests for memory structure index visibility."""

from __future__ import annotations

import argparse
import json
from unittest.mock import patch

from brain.presentation.actions.memory import command_memory_structure


TREE_WITH_INDEXES = {
    "profiles": {
        "__type__": "dir",
        "mtime": 0.0,
        "entries": 1,
        "children": {
            "index": {
                "__type__": "file",
                "mtime": 0.0,
                "size": "1.0KB",
                "lines": "10",
                "entries": 3,
            },
        },
    },
    "index": {
        "__type__": "file",
        "mtime": 0.0,
        "size": "1.0KB",
        "lines": "10",
        "entries": 3,
    },
}


def _args(json_output: bool, color: bool = False) -> argparse.Namespace:
    """Build memory-structure command arguments."""
    return argparse.Namespace(
        color=color,
        json=json_output,
        limit=None,
        uptime_order=False,
        verbose_log=False,
    )


def test_json_structure_includes_root_and_domain_indexes(capsys) -> None:
    """Expose every index node in JSON structure output."""
    with patch.object(command_memory_structure, "load_index", return_value=TREE_WITH_INDEXES) as load_index:
        exit_code = command_memory_structure.handle(_args(json_output=True))

    paths = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert paths == ["profiles", "profiles.index", "index"]
    load_index.assert_called_once_with(include_indexes=True)


def test_colored_structure_includes_root_and_domain_indexes(capsys) -> None:
    """Expose index nodes in the colored terminal tree."""
    with patch.object(command_memory_structure, "load_index", return_value=TREE_WITH_INDEXES) as load_index:
        exit_code = command_memory_structure.handle(_args(json_output=False, color=True))

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "index" in output
    assert "profiles/" in output
    load_index.assert_called_once_with(include_indexes=True)