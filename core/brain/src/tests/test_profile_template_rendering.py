"""Regression tests for relocatable profile and memory template variables."""

from pathlib import Path

from brain.application.profiles import service


def test_local_brain_script_is_workspace_absolute_path(
    monkeypatch, tmp_path: Path
) -> None:
    """Render persisted command templates to the workspace consumer script."""
    agent_home = tmp_path / "agent"
    monkeypatch.setattr(service, "get_agent_home", lambda: agent_home)
    monkeypatch.setattr(
        service,
        "get_workspace_root",
        lambda workspace_root=None: workspace_root or tmp_path,
    )

    rendered = service.render_profile_template_variables(
        "py {LOCAL_BRAIN_SCRIPT} get-memory-entry profiles.index",
        workspace_root=tmp_path / "override",
    )

    expected = (
        (tmp_path / "override" / "$agent" / "scripts" / "brain.py").resolve().as_posix()
    )
    assert rendered == f"py '{expected}' get-memory-entry profiles.index"
    assert "$agent/scripts/brain.py" in rendered
    assert str(agent_home) not in rendered
    assert rendered.count("py ") == 1
    assert "py py" not in rendered


def test_brain_script_dir_composites_remain_workspace_localized(
    monkeypatch, tmp_path: Path
) -> None:
    """Keep BRAIN_SCRIPT_DIR composites quoted while LOCAL stays portable."""
    agent_home = tmp_path / "agent"
    monkeypatch.setattr(service, "get_agent_home", lambda: agent_home)
    monkeypatch.setattr(
        service,
        "get_workspace_root",
        lambda workspace_root=None: workspace_root or tmp_path,
    )

    rendered = service.render_profile_template_variables(
        "py {LOCAL_BRAIN_SCRIPT} and {BRAIN_SCRIPT_DIR}/brain.py"
    )

    expected = (tmp_path / "$agent" / "scripts" / "brain.py").resolve().as_posix()
    assert f"py '{expected}'" in rendered
    assert f"'{(tmp_path / '$agent' / 'scripts').as_posix()}/brain.py'" in rendered
