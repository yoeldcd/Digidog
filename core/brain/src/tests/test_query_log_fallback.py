"""Write-free regression coverage for the query-log lexical fallback."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from brain.application.logs.query_service import search_log_text_matches
from brain.application.logs.records import LogEntryRecord
from brain.presentation.actions.general.command_query import _live_policy_results
from brain.presentation.actions.logs.command_query_log import _live_policy_matches, handle


def _entry(*, record_id: int, domain: str, title: str, description: str, timestamp: str) -> LogEntryRecord:
    """Build one in-memory canonical log record."""
    return LogEntryRecord(
        timestamp=timestamp,
        domain=domain,
        title=title,
        change_type="fix",
        why="Keep search available.",
        description=description,
        impact="Users can retrieve logs.",
        record_id=record_id,
    )


def test_text_fallback_preserves_domain_and_relevance_order() -> None:
    """Lexical matches must honor domain ownership and rank exact phrases first."""
    entries = [
        _entry(record_id=1, domain="brain.logs", title="Exact", description="embedding fallback text matching", timestamp="24-07-2026 07:00 pm"),
        _entry(record_id=2, domain="brain.logs", title="Partial", description="fallback behavior", timestamp="24-07-2026 08:00 pm"),
        _entry(record_id=3, domain="avatar", title="Excluded", description="embedding fallback text matching", timestamp="24-07-2026 09:00 pm"),
    ]
    with patch("brain.application.logs.query_service.list_log_entries", return_value=entries[:2]) as list_entries:
        matches = search_log_text_matches(
            workspace_root=Path("workspace"),
            query="embedding fallback text matching",
            domain_filter="brain",
            limit=5,
            fallback_reason="embedding API unavailable",
        )
    list_entries.assert_called_once_with(workspace_root=Path("workspace"), domain="brain", newest_first=True)
    assert [match["title"] for match in matches] == ["Exact", "Partial"]
    assert matches[0]["mechanism"] == "text"
    assert matches[0]["fallback_reason"] == "embedding API unavailable"


class _UnavailableVectorStore:
    """Vector manager double that fails before index hydration."""

    def __init__(self, **_kwargs: object) -> None:
        """Accept the production constructor contract."""

    def count_records(self) -> int:
        """Raise the representative provider failure."""
        raise RuntimeError("embedding API unavailable")


def test_live_policy_results_use_policies_as_the_cli_source() -> None:
    """Query and query-log label mandatory imperative entries as policies."""
    policy = SimpleNamespace(id="rec01", text="Keep changes small.", created_at="28-07-2026 04:00 pm")
    with patch("brain.application.records.service.list_live_records", return_value=[policy]):
        query_result = _live_policy_results()[0]
        log_result = _live_policy_matches()[0]

    assert query_result.source == "policies"
    assert query_result.source_ref.domain == "policies"
    assert query_result.source_ref.read_command == "show-policies --json"
    assert query_result.source_ref.path == "$agent/data/records.json#rec01"
    assert log_result["domain"] == "policies"
    assert log_result["read_command"] == "show-policies --json"


def test_query_log_human_output_separates_policies_and_empty_matches(capsys: object) -> None:
    """Policies remain visible without being presented as matching logs."""
    policy = SimpleNamespace(id="rec01", text="Keep changes small.", created_at="28-07-2026 04:00 pm")
    args = argparse.Namespace(domain="missing", query=None, limit=2, json=False, color=False, quiet=True)
    manager = SimpleNamespace(count_records=lambda: 1, search_logs=lambda *_args, **_kwargs: [])
    with (
        patch("brain.presentation.actions.logs.command_query_log.get_workspace_root", return_value=Path("workspace")),
        patch("brain.presentation.actions.logs.command_query_log.get_vectorstore_dir", return_value=Path("unused")),
        patch("brain.presentation.actions.logs.command_query_log.VectorStoreManager", return_value=manager),
        patch("brain.application.logs.store.list_log_domains", return_value=[]),
        patch("brain.application.records.service.list_live_records", return_value=[policy]),
    ):
        assert handle(args) == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "Active workspace policies" in output
    assert "Keep changes small." in output
    assert "No matching log entries found." in output
    assert "Matching log entries" not in output


def test_query_log_command_degrades_to_text_json(capsys: object) -> None:
    """The CLI must return successful lexical results when embeddings fail."""
    entry = _entry(
        record_id=9,
        domain="brain.logs",
        title="Fallback",
        description="query log keeps text matching",
        timestamp="24-07-2026 07:30 pm",
    )
    args = argparse.Namespace(domain="text matching", query=None, limit=5, json=True, color=False, quiet=True)
    with (
        patch("brain.presentation.actions.logs.command_query_log.get_workspace_root", return_value=Path("workspace")),
        patch("brain.presentation.actions.logs.command_query_log.get_vectorstore_dir", return_value=Path("unused-vectorstore")),
        patch("brain.presentation.actions.logs.command_query_log.VectorStoreManager", _UnavailableVectorStore),
        patch("brain.application.logs.query_service.list_log_entries", return_value=[entry]),
    ):
        exit_code = handle(args)
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["command"] == "query-log"
    assert payload["counts"]["matches"] == 1
    fallback = payload["matches"][0]
    assert fallback["mechanism"] == "text"
    assert args.embedding_unavailable == "embedding API unavailable"
