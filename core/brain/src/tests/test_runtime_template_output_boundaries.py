"""Runtime template localization tests for public query and log outputs."""

from pathlib import Path

from brain.application.profiles import service as profile_service
from brain.application.querying.backends.logs import (
    _localize_result as localize_log_result,
)
from brain.application.querying.backends.memory import (
    _localize_result as localize_memory_result,
)
from brain.application.querying.dtos import (
    GlobalQueryResultDTO,
    QueryContentDTO,
    QuerySourceRefDTO,
)
from brain.presentation.actions.logs.command_query_log import _localize_match


def _expected_script(workspace_root: Path) -> str:
    """Return the canonical quoted consumer launcher used by assertions."""
    script = (workspace_root / "$agent" / "scripts" / "brain.py").resolve()
    return f"'{script.as_posix()}'"


def _result_with_templates() -> GlobalQueryResultDTO:
    """Build one result containing templates at every public text boundary."""
    command = "py {LOCAL_BRAIN_SCRIPT} get-memory-entry tools.patcher"
    return GlobalQueryResultDTO(
        source="memory",
        kind="memory",
        title=command,
        text=command,
        warning=command,
        data={"nested": {"commands": [command]}},
        content=QueryContentDTO(
            title=command,
            excerpt=command,
            body=command,
            location=command,
        ),
        source_ref=QuerySourceRefDTO(
            read_command=command,
            path=command,
            title=command,
        ),
    )


def test_recursive_template_renderer_preserves_source_data(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Localize nested JSON-compatible values without mutating the input."""
    monkeypatch.setattr(
        profile_service,
        "get_workspace_root",
        lambda workspace_root=None: workspace_root or tmp_path,
    )
    source = {"items": ["py {LOCAL_BRAIN_SCRIPT} query test"]}

    rendered = profile_service.render_profile_template_value(source, tmp_path)

    assert source["items"][0] == "py {LOCAL_BRAIN_SCRIPT} query test"
    assert isinstance(rendered, dict)
    assert _expected_script(tmp_path) in rendered["items"][0]


def test_query_backends_localize_copies_of_every_public_text_field(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Keep raw retrieval evidence unchanged while localizing returned DTOs."""
    monkeypatch.setattr(
        profile_service,
        "get_workspace_root",
        lambda workspace_root=None: workspace_root or tmp_path,
    )
    original = _result_with_templates()

    for localizer in (localize_memory_result, localize_log_result):
        localized = localizer(original)
        serialized = localized.model_dump_json()

        assert _expected_script(tmp_path) in serialized
        assert "{LOCAL_BRAIN_SCRIPT}" not in serialized
        assert "py py " not in serialized

    assert "{LOCAL_BRAIN_SCRIPT}" in original.model_dump_json()


def test_log_query_match_localizes_nested_json_output(tmp_path: Path) -> None:
    """Resolve nested match fields at the query-log output boundary."""
    source = {
        "text": "py {LOCAL_BRAIN_SCRIPT} read-log 01-01-2026",
        "metadata": {"read": "py {LOCAL_BRAIN_SCRIPT} log-index"},
    }

    localized = _localize_match(source, tmp_path)
    rendered = str(localized)

    assert _expected_script(tmp_path) in rendered
    assert "{LOCAL_BRAIN_SCRIPT}" not in rendered
    assert source["text"].startswith("py {LOCAL_BRAIN_SCRIPT}")
