# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Regression tests for deterministic Brain facade import precedence."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _load_core_module():
    """Load the canonical facade template without invoking its CLI entry point."""
    core_path = Path(__file__).resolve().parents[3] / "core_cli.py"
    spec = importlib.util.spec_from_file_location("brain_core_template", core_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_import_path_is_moved_to_front_when_already_present() -> None:
    module = _load_core_module()
    brain_src = Path(__file__).resolve().parents[1]
    existing = str(brain_src)
    with patch.object(sys, "path", ["collision", existing, "stdlib"]):
        module._prioritize_import_path(brain_src)
        module._prioritize_import_path(brain_src)
        normalized = [str(Path(item or ".").resolve()) for item in sys.path]
    assert normalized[0] == str(brain_src.resolve())
    assert normalized.count(str(brain_src.resolve())) == 1


def test_core_data_paths_do_not_derive_from_agent_dir() -> None:
    """Keep fixed core stores separate from agent-owned memory and snippets."""
    from brain.infrastructure.runtime.paths import (
        get_agent_home,
        get_brain_configs_path,
        get_global_database_dir,
        get_instruction_mirrors_registry_path,
        get_source_registry_path,
        get_vectorstore_dir,
    )

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        core_root = root / "installed-core"
        agent_dir = root / "global-agent"
        configs_dir = core_root / "configs"
        configs_dir.mkdir(parents=True)
        (configs_dir / "brain_configs.json").write_text(
            json.dumps({"version": 1, "agent_dir": str(agent_dir), "knowledge": {}, "memory": {}}),
            encoding="utf-8",
        )
        with patch(
            "brain.infrastructure.runtime.paths.get_core_root",
            return_value=core_root,
        ), patch.dict(
            "os.environ",
            {"CORE_ROOT": str(root / "wrong-core"), "AGENT_HOME": str(root / "wrong-agent")},
        ):
            assert get_agent_home() == agent_dir.resolve()
            assert get_brain_configs_path() == core_root / "configs" / "brain_configs.json"
            assert get_global_database_dir(create=False) == core_root / "database" / "knowledge"
            assert get_instruction_mirrors_registry_path(create=False) == (
                core_root / "database" / "instruction_mirrors" / "agent_prompt_mirrors.txt"
            )
            assert get_source_registry_path(scope="global") == core_root / "database" / "sources" / "brain_sources.db"
            assert get_vectorstore_dir(scope="global", create=False) == core_root / "database" / "vectorstores"


def load_tests(loader, tests, pattern):
    """Expose the function-style path regressions to unittest discovery."""
    del loader, tests, pattern
    return unittest.TestSuite(
        (
            unittest.FunctionTestCase(test_import_path_is_moved_to_front_when_already_present),
            unittest.FunctionTestCase(test_core_data_paths_do_not_derive_from_agent_dir),
        )
    )
