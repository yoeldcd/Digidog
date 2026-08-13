"""Consumer workspace-root resolution contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from brain.infrastructure.runtime.migrations.migration_service import (
    migrate_brain_runtime_stores,
)
from brain.infrastructure.runtime.paths import (
    get_local_database_dir,
    get_workspace_root,
)


def test_explicit_workspace_root_does_not_require_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve an explicit consumer without consulting the process directory."""
    monkeypatch.delenv("WORKSPACE_ROOT", raising=False)

    assert get_workspace_root(workspace_root=tmp_path) == tmp_path.resolve()


def test_environment_workspace_root_is_resolved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve the consumer root exported by its local Brain facade."""
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))

    assert get_workspace_root() == tmp_path.resolve()


@pytest.mark.parametrize("configured_value", [None, "", "   "])
def test_missing_workspace_root_fails_without_creating_local_storage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configured_value: str | None,
) -> None:
    """Reject absent consumer context before deriving storage from the cwd."""
    if configured_value is None:
        monkeypatch.delenv("WORKSPACE_ROOT", raising=False)
    else:
        monkeypatch.setenv("WORKSPACE_ROOT", configured_value)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError, match="consumer.*facade"):
        get_local_database_dir()

    assert not (tmp_path / "$agent").exists()


def test_runtime_migration_rejects_missing_consumer_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prevent migration setup from treating its process cwd as a consumer."""
    monkeypatch.delenv("WORKSPACE_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError, match="consumer.*facade"):
        migrate_brain_runtime_stores(agent_home=tmp_path / "agent")

    assert not (tmp_path / "$agent").exists()
