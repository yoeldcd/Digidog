from __future__ import annotations

import json
from pathlib import Path

import pytest

from brain.infrastructure.runtime.paths import get_transient_dir


def _write_config(core_root: Path, value: object) -> None:
    config_dir = core_root / "configs"
    config_dir.mkdir(parents=True)
    (config_dir / "brain_configs.json").write_text(json.dumps({"transient_dir": value}), encoding="utf-8")


def test_configured_absolute_base_returns_patch_child(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    core_root = tmp_path / "core"
    configured_base = tmp_path / "configured"
    configured_base.mkdir()
    _write_config(core_root, str(configured_base))

    result = get_transient_dir(workspace_root=workspace, core_root=core_root)

    assert result == configured_base / "patches_rollback"
    assert result.is_dir()
    assert result != configured_base
    assert not (workspace / "$agent" / "tmp" / "patches_rollback").exists()


@pytest.mark.parametrize("value", [None, "", "relative/path", {"nested": True}])
def test_invalid_config_falls_back_to_workspace_tmp(tmp_path: Path, value: object) -> None:
    workspace = tmp_path / "workspace"
    core_root = tmp_path / "core"
    _write_config(core_root, value)

    result = get_transient_dir(workspace_root=workspace, core_root=core_root)

    expected = workspace / "$agent" / ".tmp" / "patches_rollback"
    assert result == expected
    assert result.is_dir()
    assert not (workspace / "$agent" / "tmp" / "patches_rollback").exists()


def test_file_configured_base_falls_back(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    core_root = tmp_path / "core"
    configured_file = tmp_path / "configured-file"
    configured_file.write_text("not a directory", encoding="utf-8")
    _write_config(core_root, str(configured_file))

    result = get_transient_dir(workspace_root=workspace, core_root=core_root)

    assert result == workspace / "$agent" / ".tmp" / "patches_rollback"
    assert result.is_dir()


def test_patch_child_creation_failure_is_propagated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    core_root = tmp_path / "core"

    original_mkdir = Path.mkdir

    def failing_mkdir(self: Path, *args: object, **kwargs: object) -> None:
        if self.name == "patches_rollback":
            raise OSError("creation denied")
        original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", failing_mkdir)

    with pytest.raises(OSError, match="creation denied"):
        get_transient_dir(workspace_root=workspace, core_root=core_root)
