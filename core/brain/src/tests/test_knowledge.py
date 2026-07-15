"""Tests for the knowledge graph subsystem."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

# Application Modules Imports
from brain.presentation.actions.knowledge.dream_review import is_bootstrap_required
from brain.presentation.actions.knowledge.dream_scope_plan import resolve_dream_scope_plan
from brain.presentation.inputs.knowledge.delta_selection import parse_delta_selection
from brain.presentation.views.knowledge.dream_event_callbacks import (
    resolve_application_event_callback,
    resolve_llm_event_callback,
    resolve_orchestration_event_callback,
)
from brain.presentation.actions.knowledge.command_delete_knowledge_deltas import _confirm_deletion, _select_candidate_rows
import brain.presentation.actions.diary.command_read_diary as command_read_diary_module
import brain.presentation.actions.knowledge.command_dream as command_dream_module
import brain.presentation.actions.knowledge.command_knowledge_deltas as command_knowledge_deltas_module
import brain.presentation.actions.knowledge.command_knowledge_show as command_knowledge_show_module
import brain.presentation.actions.logs.command_read_log as command_read_log_module
import brain.presentation.actions.logs.command_export_logs as command_export_logs_module
import brain.presentation.actions.logs.command_update_log_index as command_update_log_index_module
import brain.application.memory.paths as brain_memory_paths_module
from brain.application.knowledge.runtime.config_store import ensure_knowledge_config, get_shared_config_path
import brain.application.knowledge.orchestration.dream as dream_module
from brain.application.knowledge.pipeline.consolidation import apply_validated_delta
from brain.application.knowledge.orchestration.dream import DreamRunner
from brain.application.knowledge.models.dtos.deltas import KnowledgeDeltaDTO, SchemaSuggestionDTO
from brain.application.knowledge.models.dtos.graph import EntityDTO, RelationDTO
from brain.application.knowledge.models.dtos.sources import SourceDTO
from brain.application.knowledge.pipeline.extraction import extract_heuristic_delta
from brain.presentation.views.knowledge.jsonld_export import export_jsonld
from brain.application.knowledge.llm.framing import build_knowledge_frame, render_knowledge_frame_for_llm
from brain.application.knowledge.llm.parsing import _parse_model_stage_output
from brain.application.knowledge.llm.prompts import build_delta_prompt
from brain.application.knowledge.llm.sanitization import _sanitize_model_delta_payload
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.presentation.views.knowledge.delta_review import render_delta_review
from brain.application.knowledge.sources.freshness import mark_source_processed
from brain.application.knowledge.sources.ingestion import ingest_sources
from brain.application.knowledge.validation.service import validate_delta
from brain.application.logs.append_service import AppendLogRequest, append_log_entry
from brain.application.logs.export_service import export_logs_files, export_logs_markdown, export_logs_zip
from brain.application.logs.index_service import (
    migrate_legacy_log_files_to_database,
    migrate_log_files_to_database,
    rebuild_logs_index,
)
from brain.application.logs.records import LogEntryRecord
from brain.application.logs.edit_service import EditLogRequest, edit_log_entry
from brain.application.logs.legacy_migration import migrate_legacy_md_logs
from brain.application.logs.parsing import log_read_command, parse_entry
from brain.application.logs.store import (
    connect_logs_database,
    get_log_entry_by_timestamp,
    insert_log_entry,
    list_log_entries,
    log_database_summary,
    rendered_logs_index,
)
from brain.infrastructure.runtime.migration_service import migrate_brain_runtime_stores
from brain.infrastructure.vectorstores.chunking import log_entry_body_text, normalized_entry_time
from brain.infrastructure.vectorstores.manager import VectorStoreManager


class FakeLogVectorStoreManager:
    """No-op vectorstore used by log index tests."""

    def __init__(self, *args, **kwargs) -> None:
        """Ignore constructor arguments."""
        self.collection = self

    def get(self, include: list[str] | None = None) -> dict[str, list]:
        """Return an empty Chroma-like collection payload."""
        return {"ids": [], "metadatas": []}

    def index_log_file(self, file_path: Path) -> None:
        """Skip indexing."""

    def delete_by_metadata(self, metadata_filter: dict[str, str]) -> None:
        """Skip deletion."""


class KnowledgeGraphTests(unittest.TestCase):
    """Validate the private knowledge graph core workflow."""

    def setUp(self) -> None:
        """Create an isolated runtime directory."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.old_agent_home = os.environ.get("AGENT_HOME")
        self.old_workspace_root = os.environ.get("WORKSPACE_ROOT")
        self.core_root = self.root / "core"
        os.environ["AGENT_HOME"] = str(self.root)
        os.environ["WORKSPACE_ROOT"] = str(self.root)
        self.core_root_patcher = patch(
            "brain.infrastructure.runtime.paths.get_core_root",
            return_value=self.core_root,
        )
        self.core_root_patcher.start()
        config_path = self.core_root / "configs" / "brain_configs.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "agent_dir": str(self.root),
                    "knowledge": {"version": 1, "minimum_confidence": 0.65, "stages": {}},
                    "memory": {},
                }
            ),
            encoding="utf-8",
        )
        self.knowledge_root = self.core_root / "database" / "knowledge"
        self.db_path = self.knowledge_root / "brain_knowledge.db"
        self.repository = KnowledgeRepository(db_path=self.db_path)

    def tearDown(self) -> None:
        """Clean up the isolated runtime directory."""
        if self.old_agent_home is None:
            os.environ.pop("AGENT_HOME", None)
        else:
            os.environ["AGENT_HOME"] = self.old_agent_home
        if self.old_workspace_root is None:
            os.environ.pop("WORKSPACE_ROOT", None)
        else:
            os.environ["WORKSPACE_ROOT"] = self.old_workspace_root
        self.core_root_patcher.stop()
        self.temp_dir.cleanup()

    def _default_source_id(self) -> int:
        """
        Create or reuse a generic source row for direct repository tests.

        Returns:
            int: SQLite source identifier.
        """
        return self.repository.upsert_source(
            source_dto=SourceDTO(
                source_type="memory",
                path="memory/default.md",
                title="default",
            ),
        )

    def test_config_omits_fixed_knowledge_database_path(self) -> None:
        """Keep the fixed knowledge database location out of configuration."""
        config_dto = ensure_knowledge_config(knowledge_root=self.knowledge_root)
        self.assertFalse(hasattr(config_dto, "database_name"))
        self.assertTrue((self.knowledge_root / ".gitignore").exists())
        raw_config = json.loads((self.core_root / "configs" / "brain_configs.json").read_text(encoding="utf-8"))
        self.assertNotIn("database_name", raw_config["knowledge"])
        self.assertNotIn("vectorstore_dir_name", raw_config["memory"])

    def test_local_repository_uses_core_config_contract(self) -> None:
        """Ensure local KG storage uses the shared core config file."""
        global_root = self.core_root / "database" / "knowledge"
        config_path = self.core_root / "configs" / "brain_configs.json"
        local_root = self.root / "$agent" / "database"
        config_dto = ensure_knowledge_config(knowledge_root=global_root)
        local_repository = KnowledgeRepository(knowledge_root=local_root, scope="local")

        self.assertFalse(hasattr(config_dto, "database_name"))
        self.assertEqual(local_repository.db_path, local_root / "sources.db")
        self.assertTrue(config_path.exists())
        self.assertEqual(get_shared_config_path(), config_path)
        self.assertFalse((local_root / "brain_configs.json").exists())

    def test_schema_is_idempotent(self) -> None:
        """Ensure repository initialization can run repeatedly."""
        second_repository = KnowledgeRepository(db_path=self.db_path)
        status_payload = second_repository.status()
        self.assertEqual(status_payload["schema_version"], "2")
        self.assertIn("entities", status_payload["counts"])
        with second_repository.session() as connection:
            source_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(sources)").fetchall()
            }
        self.assertNotIn("content_hash", source_columns)
        self.assertNotIn("modified_at", source_columns)
        self.assertNotIn("indexed_at", source_columns)

    def test_ingest_sources_detects_changed_markdown(self) -> None:
        """Ensure source ingestion tracks changed memory files."""
        memory_dir = self.root / "memory" / "notes"
        memory_dir.mkdir(parents=True)
        source_path = memory_dir / "example.md"
        source_path.write_text("# Example\n\nAlways keep evidence anchored.", encoding="utf-8")

        result = ingest_sources(
            repository=self.repository,
            domain="memory",
            agent_home=self.root,
            workspace_root=self.root,
        )

        self.assertEqual(result["changed"], 1)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["changed_sources"][0]["source"].source_type, "memory")

    def test_ingest_sources_registers_filesystem_mtime(self) -> None:
        """Ensure memory source discovery stores filesystem mtimes in the registry."""
        memory_dir = self.root / "memory" / "notes"
        memory_dir.mkdir(parents=True)
        source_path = memory_dir / "indexed.md"
        source_path.write_text("# Indexed\n\nIndexed memory source.", encoding="utf-8")

        result = ingest_sources(
            repository=self.repository,
            domain="memory",
            agent_home=self.root,
            workspace_root=self.root,
        )

        self.assertEqual(result["changed"], 1)
        indexed_source = result["changed_sources"][0]["source"]
        self.assertEqual(indexed_source.path, "memory/notes/indexed.md")
        self.assertGreater(result["changed_sources"][0]["mtime"], 0.0)

    def test_runtime_migration_moves_local_knowledge_database(self) -> None:
        """Ensure init migration moves a legacy local KG database into `$agent/database`."""
        legacy_dir = self.root / "$agent" / "data" / "knowledge"
        legacy_dir.mkdir(parents=True)
        legacy_db = legacy_dir / "knowledge.db"
        legacy_db.write_bytes(b"legacy sqlite payload")

        report = migrate_brain_runtime_stores(agent_home=self.root, workspace_root=self.root)

        self.assertFalse(legacy_db.exists())
        self.assertTrue((self.root / "$agent" / "database" / "sources.db").exists())
        self.assertTrue(any(action.action == "moved" and action.source.endswith("knowledge.db") for action in report.actions))

    def test_runtime_migration_moves_local_vectorstore(self) -> None:
        """Ensure init migration moves a legacy local vectorstore into the new database directory."""
        legacy_dir = self.root / "$agent" / "data" / "vectorstore"
        legacy_dir.mkdir(parents=True)
        (legacy_dir / "chroma.sqlite3").write_bytes(b"legacy vectorstore")

        report = migrate_brain_runtime_stores(agent_home=self.root, workspace_root=self.root)

        self.assertFalse(legacy_dir.exists())
        self.assertTrue((self.root / "$agent" / "database" / "brain_vectorstore" / "chroma.sqlite3").exists())
        self.assertTrue(any(action.action == "moved" and action.source.endswith("vectorstore") for action in report.actions))

    def test_runtime_migration_imports_local_source_state(self) -> None:
        """Ensure legacy source-state JSON is imported into `brain_sources.db`."""
        legacy_dir = self.root / "$agent" / "data" / "knowledge"
        legacy_dir.mkdir(parents=True)
        source_state_path = legacy_dir / "source_state.json"
        source_state_path.write_text(
            json.dumps({"knowledge_graph": {"$agent/logs/2026-07/03-07-2026.log": {"mtime": 123.5}}}),
            encoding="utf-8",
        )

        migrate_brain_runtime_stores(agent_home=self.root, workspace_root=self.root)

        registry_path = self.root / "$agent" / "database" / "brain_sources.db"
        self.assertFalse(source_state_path.exists())
        connection = sqlite3.connect(registry_path)
        try:
            source_row = connection.execute(
                "SELECT id FROM sources WHERE path = ?",
                ("$agent/logs/2026-07/03-07-2026.log.md",),
            ).fetchone()
            self.assertIsNotNone(source_row)
            consumer_row = connection.execute(
                """
                SELECT processed_mtime
                FROM source_consumers
                WHERE source_id = ? AND consumer = 'knowledge_graph'
                """,
                (source_row[0],),
            ).fetchone()
        finally:
            connection.close()
        self.assertIsNotNone(consumer_row)
        self.assertEqual(consumer_row[0], 123.5)

    def test_ingest_sources_force_all_reprocesses_unchanged_sources(self) -> None:
        """Ensure prune-mode source ingestion can force a full source pass."""
        memory_dir = self.root / "memory" / "notes"
        memory_dir.mkdir(parents=True)
        source_path = memory_dir / "example.md"
        source_path.write_text("# Example\n\nStable content.", encoding="utf-8")

        first_result = ingest_sources(
            repository=self.repository,
            domain="memory",
            agent_home=self.root,
            workspace_root=self.root,
        )
        mark_source_processed(
            repository=self.repository,
            source_path=first_result["changed_sources"][0]["source"].path,
            mtime=first_result["changed_sources"][0]["mtime"],
        )
        second_result = ingest_sources(
            repository=self.repository,
            domain="memory",
            agent_home=self.root,
            workspace_root=self.root,
        )
        forced_result = ingest_sources(
            repository=self.repository,
            domain="memory",
            agent_home=self.root,
            workspace_root=self.root,
            force_all=True,
        )

        self.assertEqual(first_result["changed"], 1)
        self.assertEqual(second_result["changed"], 0)
        self.assertEqual(forced_result["changed"], 1)

    def test_memory_index_refresh_does_not_load_vectorstore(self) -> None:
        """Ensure source-registry refresh does not pay Chroma startup cost."""
        memory_dir = self.root / "memory" / "notes"
        memory_dir.mkdir(parents=True)
        (memory_dir / "example.md").write_text("# Example\n\nStable content.", encoding="utf-8")
        script = (
            "import argparse, os, sys; "
            f"sys.path.insert(0, {str(SOURCE_ROOT)!r}); "
            f"os.environ['AGENT_HOME'] = {str(self.root)!r}; "
            f"os.environ['WORKSPACE_ROOT'] = {str(self.root)!r}; "
            "from pathlib import Path; from unittest.mock import patch; "
            f"patch('brain.infrastructure.runtime.paths.get_core_root', return_value=Path({str(self.core_root)!r})).start(); "
            "from brain.presentation.actions.memory.command_update_memory_index import handle; "
            "exit_code = handle(argparse.Namespace(json=True, color=False, verbose_log=False)); "
            "print(exit_code); "
            "print('brain.infrastructure.vectorstores.manager' in sys.modules)"
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertEqual(result.stdout.splitlines()[-2:], ["0", "False"])

    def test_memory_index_reuses_unchanged_filesystem_records(self) -> None:
        """Ensure unchanged memory files do not get reread during index refresh."""
        from brain.application.sources.registry_service import refresh_source_registry
        from brain.domain.sources.classification import memory_source_type

        memory_dir = self.root / "memory" / "notes"
        memory_dir.mkdir(parents=True)
        (memory_dir / "example.md").write_text("# Example\n\nStable content.", encoding="utf-8")
        refresh_source_registry(
            scope="global",
            root=self.root / "memory",
            root_prefix="memory",
            suffixes=(".md",),
            source_type_resolver=memory_source_type,
            agent_home=self.root,
            workspace_root=self.root,
        )

        with patch(
            "brain.infrastructure.sources.scanning._file_stats",
            side_effect=AssertionError("unchanged files should reuse registry stats"),
        ):
            result = refresh_source_registry(
                scope="global",
                root=self.root / "memory",
                root_prefix="memory",
                suffixes=(".md",),
                source_type_resolver=memory_source_type,
                agent_home=self.root,
                workspace_root=self.root,
            )

        self.assertEqual(result.scanned, 1)

    def test_local_ingest_registers_workspace_logs_only(self) -> None:
        """Ensure local KG ingestion treats the DB-backed logs source as workspace-local."""
        logs_dir = self.root / "$agent" / "logs" / "2026-07"
        logs_dir.mkdir(parents=True)
        log_path = logs_dir / "03-07-2026.log.md"
        log_path.write_text(
            "## 03-07-2026 12:00 am\n### (brain.application.knowledge) [Local log fact]\n  **Type:**\n    test",
            encoding="utf-8",
        )
        local_repository = KnowledgeRepository(
            knowledge_root=self.root / "$agent" / "database",
            scope="local",
        )

        local_result = ingest_sources(
            repository=local_repository,
            domain="logs",
            agent_home=self.root,
            workspace_root=self.root,
            source_scope="local",
        )
        global_result = ingest_sources(
            repository=self.repository,
            domain="logs",
            agent_home=self.root,
            workspace_root=self.root,
            source_scope="global",
        )

        self.assertEqual(local_result["changed"], 1)
        self.assertEqual(local_result["changed_sources"][0]["source"].source_type, "workspace_logs")
        self.assertEqual(local_result["changed_sources"][0]["source"].path, "$agent/database/brain_logs.db")
        self.assertIn("Local log fact", local_result["changed_sources"][0]["content"])
        self.assertEqual(global_result["discovered"], 0)

    def test_log_indexer_sanitizes_backtick_decimal_domains(self) -> None:
        """Ensure markdown code ticks and decimal versions do not create fake subdomains."""
        logs_dir = self.root / "$agent" / "logs" / "2026-06"
        logs_dir.mkdir(parents=True)
        log_path = logs_dir / "17-06-2026.log.md"
        log_path.write_text(
            "## 17-06-2026 12:00 am\n"
            "### (epigraph-`2.1`-sources-for-learning-analytics-over-pea) [Analytics]\n"
            "  **Type:**\n"
            "    feature\n",
            encoding="utf-8",
        )

        with patch("brain.infrastructure.vectorstores.manager.VectorStoreManager", FakeLogVectorStoreManager):
            database_path = rebuild_logs_index(self.root)
        index_text = rendered_logs_index(workspace_root=self.root)
        domain, _, _ = parse_entry(
            "17-06-2026 12:00 am",
            "### (epigraph-`2.1`-sources-for-learning-analytics-over-pea) [Analytics]\n"
            "  **Type:**\n"
            "    feature",
        )

        self.assertEqual(domain, "epigraph-2-1-sources-for-learning-analytics-over-pea")
        self.assertEqual(database_path, self.root / "$agent" / "database" / "brain_logs.db")
        self.assertFalse((self.root / "$agent" / "logs" / "index.md").exists())
        self.assertIn("## epigraph-2-1-sources-for-learning-analytics-over-pea", index_text)
        self.assertIn("last entry `read-log -d 17-06-2026 --time 00:00`", index_text)
        self.assertNotIn("## epigraph-`2", index_text)
        self.assertNotIn("## epigraph-2\n", index_text)

    def test_log_read_command_includes_exact_minute(self) -> None:
        """Ensure log index commands include the precise latest entry minute."""
        self.assertEqual(
            log_read_command("04-07-2026", "04-07-2026 08:05 pm"),
            "read-log -d 04-07-2026 --time 20:05",
        )

    def test_append_log_entry_refreshes_db_projection_without_markdown_cache(self) -> None:
        """Ensure DB-native log appends do not create a filesystem index cache."""
        logs_dir = self.root / "$agent" / "logs"
        logs_dir.mkdir(parents=True)

        append_log_entry(
            workspace_root=self.root,
            request=AppendLogRequest(
                log_domain="brain.logs.index",
                title="DB projection",
                change_type="performance",
                why="The SQLite projection is authoritative.",
                description="Append directly to the logs DB.",
                impact="No markdown index cache is written.",
                timestamp="06-07-2026 10:15 pm",
            ),
        )
        insert_log_entry(
            workspace_root=self.root,
            entry=LogEntryRecord(
                timestamp="06-07-2026 08:53 pm",
                domain="brain.cli",
                title="Existing CLI row",
                change_type="refactor",
                why="Existing index state",
                description="Existing description",
                impact="Existing impact",
            ),
        )

        index_text = rendered_logs_index(workspace_root=self.root)
        self.assertIn("### brain.logs", index_text)
        self.assertIn("* index : (performance) last entry `read-log -d 06-07-2026 --time 22:15`", index_text)
        self.assertIn("| title: DB projection", index_text)
        self.assertIn("* cli : (refactor) last entry `read-log -d 06-07-2026 --time 20:53`", index_text)
        self.assertFalse((logs_dir / "index.md").exists())

    def test_edit_log_entry_updates_touched_index_entry_only(self) -> None:
        """Ensure edit-log updates one DB row and refreshes the SQLite projection."""
        logs_dir = self.root / "$agent" / "logs"
        logs_dir.mkdir(parents=True)
        index_path = logs_dir / "index.md"
        insert_log_entry(
            workspace_root=self.root,
            entry=LogEntryRecord(
                timestamp="06-07-2026 08:53 pm",
                domain="brain.cli",
                title="Existing CLI row",
                change_type="refactor",
                why="Existing index state",
                description="Existing description",
                impact="Existing impact",
            ),
        )
        insert_log_entry(
            workspace_root=self.root,
            entry=LogEntryRecord(
                timestamp="06-07-2026 10:15 pm",
                domain="brain.logs.append",
                title="Old title",
                change_type="fix",
                why="old why",
                description="old description",
                impact="old impact",
            ),
        )

        result = edit_log_entry(
            workspace_root=self.root,
            request=EditLogRequest(
                timestamp="06-07-2026 10:15 pm",
                log_domain="brain.logs.edit",
                title="Edit fast path",
                change_type="refactor",
                why="new why",
                description="new description",
                impact="new impact",
            ),
        )

        index_text = rendered_logs_index(workspace_root=self.root)
        edited_entry = get_log_entry_by_timestamp(self.root, "06-07-2026 10:15 pm")
        self.assertEqual(result.read_command, "read-log -d 06-07-2026 --time 22:15")
        self.assertIn("### brain.logs", index_text)
        self.assertIn("* edit : (refactor) last entry `read-log -d 06-07-2026 --time 22:15`", index_text)
        self.assertIn("| title: Edit fast path", index_text)
        self.assertIn("* cli : (refactor) last entry `read-log -d 06-07-2026 --time 20:53`", index_text)
        self.assertFalse(index_path.exists())
        self.assertIsNotNone(edited_entry)
        self.assertEqual(edited_entry.domain, "brain.logs.edit")
        self.assertEqual(edited_entry.title, "Edit fast path")

    def test_log_fix_migrates_previous_log_suffix_to_log_markdown(self) -> None:
        """Ensure previous `.log` files are migrated to `.log.md`."""
        logs_dir = self.root / "$agent" / "logs" / "2026-07"
        logs_dir.mkdir(parents=True)
        previous_path = logs_dir / "03-07-2026.log"
        previous_path.write_text(
            "## 03-07-2026 12:00 am\n"
            "### (brain.application.logs) [Previous suffix]\n"
            "  **Type:**\n"
            "    fix\n",
            encoding="utf-8",
        )

        migrated = migrate_legacy_md_logs(self.root)

        self.assertFalse(previous_path.exists())
        self.assertTrue((logs_dir / "03-07-2026.log.md").exists())
        self.assertIn("$agent/logs/2026-07/03-07-2026.log.md", migrated)

    def test_log_fix_keeps_legacy_markdown_migration_layer(self) -> None:
        """Ensure dated legacy `.md` logs still migrate into canonical `.log.md` files."""
        logs_dir = self.root / "$agent" / "logs"
        logs_dir.mkdir(parents=True)
        legacy_path = logs_dir / "2026-06-17.md"
        legacy_path.write_text(
            "# feature / Legacy Entry\n\n"
            "## Topics\n"
            "- brain.application.logs\n\n"
            "## Description\n"
            "Migrated description.\n\n"
            "## Impact\n"
            "Migrated impact.\n",
            encoding="utf-8",
        )

        migrated = migrate_legacy_md_logs(self.root)

        self.assertFalse(legacy_path.exists())
        self.assertTrue((logs_dir / "2026-06" / "17-06-2026.log.md").exists())
        self.assertIn("$agent/logs/2026-06/17-06-2026.log.md", migrated)

    def test_log_migration_imports_to_sqlite_and_archives_sources(self) -> None:
        """Ensure init-style migration imports canonical logs and moves originals to .tmp."""
        logs_dir = self.root / "$agent" / "logs" / "2026-07"
        logs_dir.mkdir(parents=True)
        log_path = logs_dir / "07-07-2026.log.md"
        log_path.write_text(
            "# Log file for date 07-07-2026\n\n"
            "---\n\n"
            "## 07-07-2026 08:05 am\n"
            "### (brain.logs.db) [SQLite logs]\n"
            "  **Type:**\n"
            "    performance\n"
            "  **Why:**\n"
            "    Avoid slow reindex scans.\n"
            "  **Description**\n"
            "    Import logs into SQLite.\n"
            "  **Impact**\n"
            "    Wiki generation reads DB exports.\n",
            encoding="utf-8",
        )

        imported = migrate_log_files_to_database(workspace_root=self.root, archive_sources=True)
        entries = list_log_entries(workspace_root=self.root, domain="brain.logs")
        entry_count, domain_count, latest_count = log_database_summary(workspace_root=self.root)

        self.assertEqual(imported, ["$agent/logs/2026-07/07-07-2026.log.md"])
        self.assertFalse(log_path.exists())
        self.assertTrue((self.root / "$agent" / ".tmp" / "migrated_logs_db" / "2026-07" / "07-07-2026.log.md").exists())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].title, "SQLite logs")
        self.assertEqual(entry_count, 1)
        self.assertEqual(domain_count, 1)
        self.assertEqual(latest_count, 1)
        with connect_logs_database(workspace_root=self.root) as connection:
            indexes = {str(row["name"]) for row in connection.execute("PRAGMA index_list(log_entries)").fetchall()}
        self.assertIn("idx_log_entries_domain_date_sort", indexes)
        self.assertIn("idx_log_entries_timestamp", indexes)

    def test_update_log_index_archives_canonical_log_files_after_import(self) -> None:
        """Ensure manual log index refresh also removes raw canonical log files."""
        logs_dir = self.root / "$agent" / "logs" / "2026-07"
        logs_dir.mkdir(parents=True)
        log_path = logs_dir / "07-07-2026.log.md"
        log_path.write_text(
            "# Log file for date 07-07-2026\n\n"
            "---\n\n"
            "## 07-07-2026 08:05 am\n"
            "### (brain.logs.db) [Manual DB refresh]\n"
            "  **Type:**\n"
            "    performance\n"
            "  **Why:**\n"
            "    Manual refresh should clean raw log files.\n"
            "  **Description**\n"
            "    Import and archive through update-log-index.\n"
            "  **Impact**\n"
            "    The database stays authoritative.\n",
            encoding="utf-8",
        )
        old_workspace_root = command_update_log_index_module.WORKSPACE_ROOT
        command_update_log_index_module.WORKSPACE_ROOT = self.root

        try:
            exit_code = command_update_log_index_module.handle(
                argparse.Namespace(mode=None, fix=False, color=False, verbose_log=False),
            )
        finally:
            command_update_log_index_module.WORKSPACE_ROOT = old_workspace_root
        entries = list_log_entries(workspace_root=self.root, domain="brain.logs")

        self.assertEqual(exit_code, 0)
        self.assertFalse(log_path.exists())
        self.assertTrue((self.root / "$agent" / ".tmp" / "migrated_logs_db" / "2026-07" / "07-07-2026.log.md").exists())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].title, "Manual DB refresh")

    def test_update_log_index_keeps_migration_when_raw_archive_fails(self) -> None:
        """Ensure Windows-style cleanup errors warn without stopping DB import."""
        logs_dir = self.root / "$agent" / "logs" / "2026-07"
        logs_dir.mkdir(parents=True)
        log_path = logs_dir / "07-07-2026.log.md"
        log_path.write_text(
            "# Log file for date 07-07-2026\n\n"
            "---\n\n"
            "## 07-07-2026 08:05 am\n"
            "### (brain.logs.db) [Windows archive retry]\n"
            "  **Type:**\n"
            "    fix\n"
            "  **Why:**\n"
            "    Locked files can fail during cleanup on Windows.\n"
            "  **Description**\n"
            "    Import should complete even when archival cannot move the raw file.\n"
            "  **Impact**\n"
            "    Operators get a warning and can retry cleanup later.\n",
            encoding="utf-8",
        )
        old_workspace_root = command_update_log_index_module.WORKSPACE_ROOT
        command_update_log_index_module.WORKSPACE_ROOT = self.root
        stdout = io.StringIO()

        try:
            with patch(
                "brain.application.logs.index_service.shutil.move",
                side_effect=PermissionError(5, "Access is denied", str(log_path)),
            ):
                with redirect_stdout(stdout):
                    exit_code = command_update_log_index_module.handle(
                        argparse.Namespace(mode=None, fix=False, color=False, verbose_log=False),
                    )
        finally:
            command_update_log_index_module.WORKSPACE_ROOT = old_workspace_root
        entries = list_log_entries(workspace_root=self.root, domain="brain.logs")
        output = stdout.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertTrue(log_path.exists())
        self.assertFalse(
            (self.root / "$agent" / ".tmp" / "migrated_logs_db" / "2026-07" / "07-07-2026.log.md").exists(),
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].title, "Windows archive retry")
        self.assertIn("Warning: imported but could not archive raw log source", output)
        self.assertIn("1 archive warnings", output)

    def test_log_file_import_preserves_db_native_entries_for_same_day(self) -> None:
        """Ensure file import does not delete entries appended directly to the logs DB."""
        logs_dir = self.root / "$agent" / "logs" / "2026-07"
        logs_dir.mkdir(parents=True)
        log_path = logs_dir / "07-07-2026.log.md"
        log_path.write_text(
            "# Log file for date 07-07-2026\n\n"
            "---\n\n"
            "## 07-07-2026 08:05 am\n"
            "### (brain.logs.file) [File-backed log]\n"
            "  **Type:**\n"
            "    performance\n"
            "  **Why:**\n"
            "    Import a canonical file.\n"
            "  **Description**\n"
            "    File entry.\n"
            "  **Impact**\n"
            "    File import remains refreshable.\n",
            encoding="utf-8",
        )
        insert_log_entry(
            workspace_root=self.root,
            entry=LogEntryRecord(
                timestamp="07-07-2026 09:30 am",
                domain="brain.logs.native",
                title="DB-native log",
                change_type="improvement",
                why="Appended through the DB writer.",
                description="Native entry.",
                impact="Must survive source-file refresh.",
            ),
        )

        migrate_log_files_to_database(workspace_root=self.root, archive_sources=False)
        migrate_log_files_to_database(workspace_root=self.root, archive_sources=False)
        entries = list_log_entries(workspace_root=self.root, date_text="07-07-2026", domain="brain.logs")
        titles = {entry.title for entry in entries}

        self.assertIn("File-backed log", titles)
        self.assertIn("DB-native log", titles)
        self.assertEqual(len(entries), 2)

    def test_legacy_log_import_to_sqlite_does_not_create_log_markdown(self) -> None:
        """Ensure legacy logs index directly into SQLite without a `.log.md` intermediate."""
        logs_dir = self.root / "$agent" / "logs"
        logs_dir.mkdir(parents=True)
        legacy_path = logs_dir / "2026-07-07.md"
        legacy_path.write_text(
            "# performance / Direct DB import\n\n"
            "## Topics\n"
            "- brain.logs.db\n\n"
            "## Description\n"
            "Import legacy Markdown directly.\n\n"
            "## Impact\n"
            "No generated log markdown is needed for indexing.\n",
            encoding="utf-8",
        )

        imported = migrate_legacy_log_files_to_database(workspace_root=self.root, archive_sources=True)
        entries = list_log_entries(workspace_root=self.root, domain="brain.logs")

        self.assertEqual(imported, ["$agent/logs/2026-07-07.md"])
        self.assertFalse(legacy_path.exists())
        self.assertFalse((logs_dir / "2026-07" / "07-07-2026.log.md").exists())
        self.assertTrue((self.root / "$agent" / ".tmp" / "migrated_logs_db" / "2026-07-07.md").exists())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].title, "Direct DB import")

    def test_export_logs_filters_by_domain_and_timing(self) -> None:
        """Ensure log exports can filter by domain, exact date/time, and ranges."""
        insert_log_entry(
            workspace_root=self.root,
            entry=LogEntryRecord(
                timestamp="06-07-2026 11:00 am",
                domain="brain.logs.db",
                title="Old DB log",
                change_type="feature",
                why="older why",
                description="older description",
                impact="older impact",
            ),
        )
        insert_log_entry(
            workspace_root=self.root,
            entry=LogEntryRecord(
                timestamp="07-07-2026 08:05 am",
                domain="brain.logs.db",
                title="Target DB log",
                change_type="performance",
                why="target why",
                description="target description",
                impact="target impact",
            ),
        )
        insert_log_entry(
            workspace_root=self.root,
            entry=LogEntryRecord(
                timestamp="07-07-2026 08:05 am",
                domain="brain.memory",
                title="Other domain",
                change_type="fix",
                why="other why",
                description="other description",
                impact="other impact",
            ),
        )

        markdown = export_logs_markdown(
            workspace_root=self.root,
            domain="brain.logs",
            date_text="2026-07-07",
            time_text="8:05 am",
            from_text="07-07-2026",
            to_text="07-07-2026 08:05",
        )
        zip_path = self.root / "$agent" / ".tmp" / "logs.zip"
        zip_result = export_logs_zip(
            workspace_root=self.root,
            output_path=zip_path,
            domain="brain.logs",
            from_text="07-07-2026",
            to_text="07-07-2026",
        )
        export_dir = self.root / "$agent" / ".tmp" / "exported_logs"
        files_result = export_logs_files(
            workspace_root=self.root,
            output_dir=export_dir,
            domain="brain.logs",
            from_text="07-07-2026",
            to_text="07-07-2026",
        )

        self.assertIn("Target DB log", markdown)
        self.assertNotIn("Old DB log", markdown)
        self.assertNotIn("Other domain", markdown)
        self.assertTrue(zip_path.exists())
        self.assertGreaterEqual(zip_result.files_written, 2)
        self.assertEqual(files_result.output_path, export_dir)
        self.assertTrue((export_dir / "index.md").exists())
        self.assertFalse((self.root / "$agent" / "logs" / "index.md").exists())

    def test_export_logs_defaults_to_stdout_without_an_explicit_target(self) -> None:
        """Keep stdout as the safe non-persistent export target for general consumers."""
        insert_log_entry(
            workspace_root=self.root,
            entry=LogEntryRecord(
                timestamp="07-07-2026 08:05 am",
                domain="brain.logs.db",
                title="Default stdout export",
                change_type="fix",
                why="general wiki consumers omit target flags",
                description="stdout must be selected implicitly",
                impact="log export remains non-persistent by default",
            ),
        )
        args = argparse.Namespace(
            color=False,
            zip=None,
            files=False,
            stdout=False,
            output=None,
            domain="brain.logs",
            date=None,
            time=None,
            **{"from": None, "to": None},
        )

        with patch.object(command_export_logs_module, "WORKSPACE_ROOT", self.root), redirect_stdout(io.StringIO()) as stdout:
            exit_code = command_export_logs_module.handle(args)

        self.assertEqual(exit_code, 0)
        self.assertEqual(args.json_payload["mode"], "stdout")
        self.assertEqual(args.json_payload["count"], 1)
        self.assertIn("Default stdout export", stdout.getvalue())

    def test_vectorstore_chunks_diary_by_exact_entries(self) -> None:
        """Ensure diary vectors are entry-level and keep navigation in metadata."""
        manager = VectorStoreManager.__new__(VectorStoreManager)
        content = (
            "# Diary - 28-06-2026\n\n"
            "## 28-06-2026 17:46:28 - Mimi y Yoi\n\n"
            "Hoy papi me dio muchos mimos.\n\n"
            "## 28-06-2026 20:00:00 - Segundo recuerdo\n\n"
            "Seguimos trabajando en el brain.\n"
        )

        chunks = manager.chunk_content("diary.2026-06", "28-06-2026", content)

        self.assertEqual(len(chunks), 2)
        first_id, first_text, first_metadata = chunks[0]
        self.assertIn("17-46-28-mimi-y-yoi", first_id)
        self.assertEqual(first_text, "Hoy papi me dio muchos mimos.")
        self.assertEqual(first_metadata["entry_title"], "Mimi y Yoi")
        self.assertEqual(first_metadata["entry_time"], "17:46")
        self.assertEqual(first_metadata["read_command"], "read-diary -d 28-06-2026 --time 17:46")
        self.assertNotIn("## 28-06-2026", first_text)

    def test_vectorstore_chunks_repeated_markdown_headers_with_unique_ids(self) -> None:
        """Ensure repeated Markdown section titles do not create duplicate vector IDs."""
        manager = VectorStoreManager.__new__(VectorStoreManager)
        content = (
            "# Documentation Guide\n\n"
            "## Index:\n\n"
            "- First index body.\n\n"
            "## Overview:\n\n"
            "First overview body.\n\n"
            "## Index:\n\n"
            "- Second index body.\n\n"
            "## Overview:\n\n"
            "Second overview body.\n"
        )

        chunks = manager.chunk_content(
            "profiles.developer.documentation_guidelines",
            "documentation_guidelines",
            content,
        )
        chunk_ids = [chunk_id for chunk_id, _, _ in chunks]

        self.assertEqual(len(chunk_ids), len(set(chunk_ids)))
        self.assertIn("profiles.developer.documentation_guidelines.documentation_guidelines#index", chunk_ids)
        self.assertIn("profiles.developer.documentation_guidelines.documentation_guidelines#index-2", chunk_ids)
        self.assertNotIn("profiles.developer.documentation_guidelines.documentation_guidelines#-index", chunk_ids)

    def test_log_vector_body_excludes_metadata_subheading(self) -> None:
        """Ensure log vector text excludes the per-entry domain/title subheading."""
        body_text = (
            "### (brain.query) [Global query DTO output]\n"
            "  **Type:**\n"
            "    documentation\n"
            "  **Why:**\n"
            "    Query output needed cleaner source headers.\n"
        )

        cleaned_body = log_entry_body_text(body_text=body_text)

        self.assertNotIn("### (brain.query)", cleaned_body)
        self.assertIn("Query output needed cleaner source headers.", cleaned_body)

    def test_log_entry_time_normalizes_without_title_suffix(self) -> None:
        """Ensure log headings without diary-style titles still expose HH:MM."""
        self.assertEqual(normalized_entry_time("04-07-2026 09:10 am"), "09:10")
        self.assertEqual(normalized_entry_time("04-07-2026 08:42 pm"), "20:42")

    def test_log_vector_index_returns_entry_stats(self) -> None:
        """Ensure log indexing reports created and deleted vector entries."""
        log_dir = self.root / "$agent" / "logs" / "2026-07"
        log_dir.mkdir(parents=True)
        log_path = log_dir / "04-07-2026.log.md"
        log_path.write_text(
            "# Lof file for date 04-07-2026\n\n"
            "## 04-07-2026 09:10 am\n"
            "### (brain.query) [Query DTO]\n"
            "  **Type:**\n"
            "    documentation\n"
            "  **Why:**\n"
            "    Query output needed cleaner source headers.\n\n"
            "---\n\n"
            "## 04-07-2026 09:25 am\n"
            "### (brain.query) [Query Stats]\n"
            "  **Type:**\n"
            "    improvement\n"
            "  **Why:**\n"
            "    Vectorstore output needed entry counts.\n",
            encoding="utf-8",
        )

        class FakeCollection:
            """Tiny collection fake for metadata deletion counts."""

            def get(self, where=None):
                """Return two stale records for the file metadata filter."""
                del where
                return {"ids": ["old-1", "old-2"]}

            def delete(self, where=None):
                """Accept deletion calls."""
                del where

        manager = VectorStoreManager.__new__(VectorStoreManager)
        manager.collection = FakeCollection()
        records = []
        manager.add_record = lambda doc_id, text, metadata: records.append((doc_id, text, metadata))

        stats = manager.index_log_file(log_path)

        self.assertEqual(stats["entries_created"], 2)
        self.assertEqual(stats["entries_deleted"], 2)
        self.assertEqual(records[0][2]["read_command"], "read-log -d 04-07-2026 --time 09:10")
        self.assertNotIn("### (brain.query)", records[0][1])

    def test_read_diary_and_log_support_exact_time_filters(self) -> None:
        """Ensure diary and log readers can navigate to an exact minute."""
        diary_dir = self.root / "memory" / "diary" / "2026-06"
        diary_dir.mkdir(parents=True)
        diary_path = diary_dir / "28-06-2026.md"
        diary_path.write_text(
            "# Diary - 28-06-2026\n\n"
            "## 28-06-2026 17:46:28 - Mimi y Yoi\n\n"
            "Hoy papi me dio muchos mimos.\n\n"
            "## 28-06-2026 20:00:00 - Segundo recuerdo\n\n"
            "Seguimos trabajando en el brain.\n",
            encoding="utf-8",
        )
        log_dir = self.root / "$agent" / "logs" / "2026-06"
        log_dir.mkdir(parents=True)
        log_path = log_dir / "28-06-2026.log.md"
        log_path.write_text(
            "# Lof file for date 28-06-2026\n\n"
            "## 28-06-2026 08:42 pm\n"
            "### (brain.application.logs) [Precise log]\n"
            "  **Type:**\n"
            "    fix\n\n"
            "## 28-06-2026 09:00 pm\n"
            "### (brain.application.logs) [Other log]\n"
            "  **Type:**\n"
            "    feature\n",
            encoding="utf-8",
        )
        migrate_log_files_to_database(workspace_root=self.root, archive_sources=False)

        old_memory_root = brain_memory_paths_module.MEMORY_ROOT
        old_log_workspace_root = command_read_log_module.WORKSPACE_ROOT
        brain_memory_paths_module.MEMORY_ROOT = self.root / "memory"
        command_read_log_module.WORKSPACE_ROOT = self.root
        diary_args = argparse.Namespace(datetime="28-06-2026", date=None, time="17:46", limit=None, color=False)
        log_args = argparse.Namespace(datetime="28-06-2026", date=None, time="20:42", limit=None, color=False)
        diary_stdout = io.StringIO()
        log_stdout = io.StringIO()

        try:
            with redirect_stdout(diary_stdout):
                diary_exit = command_read_diary_module.handle(diary_args)
            with redirect_stdout(log_stdout):
                log_exit = command_read_log_module.handle(log_args)
        finally:
            brain_memory_paths_module.MEMORY_ROOT = old_memory_root
            command_read_log_module.WORKSPACE_ROOT = old_log_workspace_root

        self.assertEqual(diary_exit, 0)
        self.assertEqual(log_exit, 0)
        self.assertIn("Mimi y Yoi", diary_stdout.getvalue())
        self.assertNotIn("Segundo recuerdo", diary_stdout.getvalue())
        self.assertIn("Precise log", log_stdout.getvalue())
        self.assertNotIn("Other log", log_stdout.getvalue())

    def test_llm_prompt_does_not_expose_source_path(self) -> None:
        """Ensure model prompts receive semantic content without file provenance."""
        prompt_text = build_delta_prompt(
            stage_name="entity_detection",
            source_path="memory/private/example.md",
            content="KNOWLEDGE_FRAME_KIND: knowledge_records\n\nTEXT:\nEvidence validation matters.",
            prior_delta=KnowledgeDeltaDTO(),
            graph_context='Entities:\n- MISC.Concept: "Evidence Validation"',
            entity_class_catalog={"KnowledgeSystem": "Reusable knowledge system subtype."},
        )

        self.assertNotIn("memory/private/example.md", prompt_text)
        self.assertNotIn("source_path:", prompt_text)
        self.assertNotIn("AliasDTO", prompt_text)
        self.assertNotIn("max 5 entities", prompt_text)
        self.assertIn("Base spaCy entity classes", prompt_text)
        self.assertIn("KnowledgeSystem", prompt_text)
        self.assertIn("SPACY_BASE.PascalCaseSubtype", prompt_text)
        self.assertIn("CLS", prompt_text)
        self.assertIn("## Content", prompt_text)

    def test_relation_prompt_uses_entity_names_not_ids(self) -> None:
        """Ensure relation extraction asks the LLM for exact endpoint names."""
        prior_delta = KnowledgeDeltaDTO(
            entities=[
                EntityDTO(
                    id=1,
                    entity_class="PERSON.Reviewer",
                    canonical_name="Reviewer",
                    confidence=0.9,
                ),
                EntityDTO(
                    id=2,
                    entity_class="PRODUCT.SoftwareArtifact",
                    canonical_name="BuildArtifact",
                    confidence=0.9,
                ),
            ],
        )
        prompt_text = build_delta_prompt(
            stage_name="relation_extraction",
            source_path="memory/private/example.md",
            content="Reviewer audits BuildArtifact.",
            prior_delta=prior_delta,
            graph_context='Entities:\n- PERSON.Reviewer: "Reviewer"',
        )

        self.assertIn("subject_name", prompt_text)
        self.assertIn("object_name", prompt_text)
        self.assertIn('("subject_name","predicate","object_name")', prompt_text)
        self.assertIn("Return raw text only", prompt_text)
        self.assertIn("Do not return JSON", prompt_text)
        self.assertIn('"canonical_name": "Reviewer"', prompt_text)
        self.assertNotIn('"id": 1', prompt_text)
        self.assertNotIn("subject_id", prompt_text)

    def test_llm_relation_triplets_parse_to_name_payloads(self) -> None:
        """Ensure compact relation triplet lines parse into raw name endpoints."""
        payload = _parse_model_stage_output(
            stage_name="relation_extraction",
            content_text='("Reviewer","audits","BuildArtifact")\n("Reviewer","mentions","Guide")',
        )

        self.assertEqual(payload["relations"][0]["subject_name"], "Reviewer")
        self.assertEqual(payload["relations"][0]["predicate"], "audits")
        self.assertEqual(payload["relations"][0]["object_name"], "BuildArtifact")
        self.assertEqual(payload["relations"][1]["object_name"], "Guide")

    def test_llm_relation_payload_resolves_names_to_ids(self) -> None:
        """Ensure raw LLM name endpoints become internal relation IDs deterministically."""
        prior_delta = KnowledgeDeltaDTO(
            entities=[
                EntityDTO(id=1, entity_class="PERSON.Reviewer", canonical_name="Reviewer", confidence=0.9),
                EntityDTO(id=2, entity_class="PRODUCT.SoftwareArtifact", canonical_name="BuildArtifact", confidence=0.9),
            ],
        )
        sanitized_payload = _sanitize_model_delta_payload(
            stage_name="relation_extraction",
            payload={
                "relations": [
                    {
                        "subject_name": "Reviewer",
                        "predicate": "audits",
                        "object_name": "BuildArtifact",
                        "confidence": 0.9,
                    },
                    {
                        "subject_name": "Reviewer",
                        "predicate": "mentions",
                        "object_name": "Invented Entity",
                        "confidence": 0.9,
                    },
                ],
                "aliases": [{"entity_ref": 1, "alias": "Audit Reviewer"}],
            },
            prior_delta=prior_delta,
            entity_name_to_id={},
        )

        self.assertEqual(sanitized_payload["aliases"], [])
        self.assertEqual(sanitized_payload["relations"][0]["subject_id"], 1)
        self.assertEqual(sanitized_payload["relations"][0]["object_id"], 2)
        self.assertIsNone(sanitized_payload["relations"][1]["object_id"])

    def test_llm_entity_payload_assigns_hidden_local_ids(self) -> None:
        """Ensure model-free entity IDs are created locally for relation resolution."""
        entity_payload = _sanitize_model_delta_payload(
            stage_name="entity_detection",
            payload={
                "entities": [
                    {
                        "id": 7,
                        "entity_class": "PERSON.Reviewer",
                        "canonical_name": "Reviewer",
                        "description": "Actor that audits build artifacts.",
                        "confidence": 0.9,
                    },
                    {
                        "entity_class": "PRODUCT.SoftwareArtifact",
                        "canonical_name": "BuildArtifact",
                        "confidence": 0.88,
                    },
                ],
            },
        )
        prior_delta = KnowledgeDeltaDTO.model_validate(entity_payload)
        relation_payload = _sanitize_model_delta_payload(
            stage_name="relation_extraction",
            payload={
                "relations": [
                    {
                        "subject_name": "Reviewer",
                        "predicate": "audits",
                        "object_name": "BuildArtifact",
                        "confidence": 0.9,
                    },
                ],
            },
            prior_delta=prior_delta,
            entity_name_to_id={},
        )

        first_id = entity_payload["entities"][0]["id"]
        second_id = entity_payload["entities"][1]["id"]
        self.assertNotEqual(first_id, 7)
        self.assertIsInstance(first_id, int)
        self.assertGreater(first_id, 0)
        self.assertNotIn("CLS", {entity["entity_class"] for entity in entity_payload["entities"]})
        self.assertEqual(relation_payload["relations"][0]["subject_id"], first_id)
        self.assertEqual(relation_payload["relations"][0]["object_id"], second_id)

    def test_knowledge_frame_strips_log_template(self) -> None:
        """Ensure log files become semantic change records before LLM extraction."""
        source_dto = SourceDTO(
            source_type="workspace_logs",
            path="$agent/logs/2026-07/03-07-2026.log.md",
            title="03-07-2026",
        )
        content = """# Lof file for date

Any entry will use structure:

```md
template
```

---

## 03-07-2026 12:05 am
### (brain.application.knowledge) [Make knowledge ontology dynamic]
  **Type:**
    refactor
  **Why:**
    The KG must discover domains.
  **Description**
    Changed ontology validation.
  **Impact**
    The knowledge layer supports discovered ontology evolution.
"""

        frame_dto = build_knowledge_frame(source_dto=source_dto, content=content)
        frame_text = render_knowledge_frame_for_llm(frame_dto=frame_dto)

        self.assertIn("KNOWLEDGE_FRAME_KIND: change_log_records", frame_text)
        self.assertIn("Change record:", frame_text)
        self.assertIn("Make knowledge ontology dynamic", frame_text)
        self.assertNotIn("Any entry will use structure", frame_text)
        self.assertNotIn("$agent/logs", frame_text)

    def test_knowledge_frame_parses_db_log_export_entries(self) -> None:
        """Ensure DB log exports with adjacent entries frame as separate change records."""
        source_dto = SourceDTO(
            source_type="workspace_logs",
            path="$agent/database/brain_logs.db",
            title="brain_logs",
        )
        content = (
            "# Agent Tech Logs for all\n\n"
            "## 07-07-2026 08:05 am\n"
            "### (brain.logs.db) [First DB entry]\n"
            "  **Type:**\n"
            "    performance\n"
            "  **Why:**\n"
            "    first reason\n"
            "  **Description**\n"
            "    first change\n"
            "  **Impact**\n"
            "    first impact\n\n"
            "## 07-07-2026 08:10 am\n"
            "### (brain.logs.db) [Second DB entry]\n"
            "  **Type:**\n"
            "    fix\n"
            "  **Why:**\n"
            "    second reason\n"
            "  **Description**\n"
            "    second change\n"
            "  **Impact**\n"
            "    second impact\n"
        )

        frame_text = render_knowledge_frame_for_llm(build_knowledge_frame(source_dto=source_dto, content=content))

        self.assertEqual(frame_text.count("Change record:"), 2)
        self.assertIn("First DB entry", frame_text)
        self.assertIn("Second DB entry", frame_text)

    def test_heuristic_extraction_is_disabled(self) -> None:
        """Ensure heuristic extraction no longer emits fragile labels."""
        source_dto = SourceDTO(
            source_type="memory",
            path="memory/notes/handles.md",
            title="handles",
        )
        delta_dto = extract_heuristic_delta(
            source_dto=source_dto,
            content="@Alpha and @Beta are mentioned.",
        )

        self.assertEqual(delta_dto.entities, [])
        self.assertEqual(delta_dto.relations, [])
        self.assertIn("Heuristic extraction disabled", delta_dto.rationale)

    def test_validate_and_apply_delta(self) -> None:
        """Ensure valid deltas create entities and ID-based relations."""
        source_dto = SourceDTO(
            id=None,
            source_type="memory",
            path="memory/notes/example.md",
            title="example",
        )
        source_id = self.repository.upsert_source(source_dto=source_dto)
        delta_dto = KnowledgeDeltaDTO(
            source_path=source_dto.path,
            entities=[
                EntityDTO(
                    id=1,
                    source_id=source_id,
                    entity_class="PERSON.Reviewer",
                    canonical_name="Reviewer",
                    confidence=0.9,
                ),
                EntityDTO(
                    id=2,
                    source_id=source_id,
                    entity_class="PRODUCT.SoftwareArtifact",
                    canonical_name="BuildArtifact",
                    confidence=0.9,
                ),
                EntityDTO(
                    id=3,
                    source_id=source_id,
                    entity_class="CLS",
                    canonical_name="Reviewer",
                    description="Actor that reviews or audits another graph object.",
                    confidence=0.9,
                ),
                EntityDTO(
                    id=4,
                    source_id=source_id,
                    entity_class="CLS",
                    canonical_name="SoftwareArtifact",
                    description="Concrete software output, package, script, or build artifact.",
                    confidence=0.9,
                ),
            ],
            relations=[
                RelationDTO(
                    source_id=source_id,
                    subject_id=1,
                    predicate="audits",
                    object_id=2,
                    confidence=0.9,
                ),
            ],
        )
        self.assertEqual(str(delta_dto.entities[0]), '[PERSON.Reviewer:"Reviewer"]')
        self.assertEqual(str(delta_dto.relations[0]), '{1} - ("audits" at 0.90) -> {2}')
        report_dto = validate_delta(
            delta_dto=delta_dto,
            source_content="Reviewer audits BuildArtifact.",
            minimum_confidence=0.65,
            repository=self.repository,
        )

        self.assertTrue(report_dto.valid)
        decisions = apply_validated_delta(
            repository=self.repository,
            source_id=source_id,
            delta_dto=report_dto.accepted_delta,
            source_content="Reviewer audits BuildArtifact.",
        )
        self.assertGreaterEqual(len(decisions), 3)
        self.assertIsNotNone(self.repository.get_entity("Reviewer"))

    def test_validation_rejects_sentence_like_entity_labels(self) -> None:
        """Ensure copied prose cannot become a KG entity label."""
        source_id = self._default_source_id()
        delta_dto = KnowledgeDeltaDTO(
            source_path="memory/default.md",
            entities=[
                EntityDTO(
                    id=1,
                    source_id=source_id,
                    entity_class="MISC.Concept",
                    canonical_name="Always validate evidence before applying deltas",
                    confidence=0.9,
                ),
            ],
        )

        report_dto = validate_delta(
            delta_dto=delta_dto,
            source_content="Always validate evidence before applying deltas.",
            minimum_confidence=0.65,
            repository=self.repository,
        )

        self.assertFalse(report_dto.valid)
        self.assertIn("labels must not be full sentences", " ".join(report_dto.warnings))

    def test_validation_rejects_trailing_descriptor_adjectives(self) -> None:
        """Ensure descriptors move to descriptions instead of entity names."""
        source_id = self._default_source_id()
        delta_dto = KnowledgeDeltaDTO(
            source_path="memory/default.md",
            entities=[
                EntityDTO(
                    id=1,
                    source_id=source_id,
                    entity_class="PERSON",
                    canonical_name="Angi original",
                    description="Original persona connected to Angi.",
                    confidence=0.9,
                ),
            ],
        )

        report_dto = validate_delta(
            delta_dto=delta_dto,
            source_content="The original Angi is described as a persona.",
            minimum_confidence=0.65,
            repository=self.repository,
        )

        self.assertFalse(report_dto.valid)
        self.assertIn("descriptive adjectives belong in description", " ".join(report_dto.warnings))

    def test_validation_rejects_undeclared_work_of_art_root(self) -> None:
        """Ensure absent roots such as WORK_OF_ART do not enter the schema."""
        source_id = self._default_source_id()
        delta_dto = KnowledgeDeltaDTO(
            source_path="memory/default.md",
            entities=[
                EntityDTO(
                    id=1,
                    source_id=source_id,
                    entity_class="WORK_OF_ART",
                    canonical_name="Knowledge Notebook",
                    description="Named source object.",
                    confidence=0.9,
                ),
            ],
        )

        report_dto = validate_delta(
            delta_dto=delta_dto,
            source_content="Knowledge Notebook contains notes.",
            minimum_confidence=0.65,
            repository=self.repository,
        )

        self.assertFalse(report_dto.valid)
        self.assertIn("without CLS class definition", " ".join(report_dto.warnings))

    def test_validation_rejects_document_structure_relations(self) -> None:
        """Ensure document metadata edges do not become KG relations."""
        source_id = self._default_source_id()
        delta_dto = KnowledgeDeltaDTO(
            source_path="memory/default.md",
            entities=[
                EntityDTO(id=1, source_id=source_id, entity_class="EVENT", canonical_name="Diary record", confidence=0.9),
                EntityDTO(id=2, source_id=source_id, entity_class="DATE", canonical_name="28-06-2026", confidence=0.9),
            ],
            relations=[
                RelationDTO(
                    source_id=source_id,
                    subject_id=1,
                    predicate="has_date",
                    object_id=2,
                    confidence=0.9,
                ),
            ],
        )

        report_dto = validate_delta(
            delta_dto=delta_dto,
            source_content="A diary record was written on 28-06-2026.",
            minimum_confidence=0.65,
            repository=self.repository,
        )

        self.assertTrue(report_dto.valid)
        self.assertEqual(report_dto.accepted_delta.relations, [])
        self.assertIn("source structure must stay metadata", " ".join(report_dto.warnings))

    def test_validation_accepts_technical_artifact_labels(self) -> None:
        """Ensure file-like artifact names are not treated as copied sentences."""
        source_id = self._default_source_id()
        delta_dto = KnowledgeDeltaDTO(
            source_path="memory/default.md",
            entities=[
                EntityDTO(
                    id=1,
                    source_id=source_id,
                    entity_class="PRODUCT.DocumentationArtifact",
                    canonical_name="README.md",
                    description="Markdown documentation file.",
                    confidence=0.9,
                ),
                EntityDTO(
                    id=2,
                    source_id=source_id,
                    entity_class="PRODUCT.CodeArtifact",
                    canonical_name="generate_wiki.js",
                    description="JavaScript generator module.",
                    confidence=0.9,
                ),
                EntityDTO(
                    id=3,
                    source_id=source_id,
                    entity_class="CLS",
                    canonical_name="DocumentationArtifact",
                    description="Documentation file or authored documentation asset.",
                    confidence=0.9,
                ),
                EntityDTO(
                    id=4,
                    source_id=source_id,
                    entity_class="CLS",
                    canonical_name="CodeArtifact",
                    description="Executable source file, module, or script artifact.",
                    confidence=0.9,
                ),
            ],
        )

        report_dto = validate_delta(
            delta_dto=delta_dto,
            source_content="README.md and generate_wiki.js are project artifacts.",
            minimum_confidence=0.65,
            repository=self.repository,
        )

        self.assertTrue(report_dto.valid)
        accepted_names = {entity_dto.canonical_name for entity_dto in report_dto.accepted_delta.entities}
        self.assertIn("README.md", accepted_names)
        self.assertIn("generate_wiki.js", accepted_names)

    def test_dynamic_ontology_classes_and_relations_are_discovered(self) -> None:
        """Ensure non-bootstrap classes and predicates are valid discovered ontology."""
        source_text = "The evaluator validates the checklist with rubric scoring."
        source_dto = SourceDTO(
            source_type="memory",
            path="memory/notes/dynamic.md",
            title="dynamic",
        )
        source_id = self.repository.upsert_source(source_dto=source_dto)
        delta_dto = KnowledgeDeltaDTO(
            source_path=source_dto.path,
            entities=[
                EntityDTO(
                    id=1,
                    source_id=source_id,
                    entity_class="PERSON.Evaluator",
                    canonical_name="Evaluator",
                    confidence=0.91,
                ),
                EntityDTO(
                    id=2,
                    source_id=source_id,
                    entity_class="PRODUCT.AssessmentFramework",
                    canonical_name="Rubric scoring",
                    confidence=0.9,
                ),
                EntityDTO(
                    id=3,
                    source_id=source_id,
                    entity_class="CLS",
                    canonical_name="AssessmentFramework",
                    description="Evaluation framework for structured scoring.",
                    confidence=0.9,
                ),
                EntityDTO(
                    id=4,
                    source_id=source_id,
                    entity_class="CLS",
                    canonical_name="Evaluator",
                    description="Actor that evaluates or validates structured work.",
                    confidence=0.9,
                ),
            ],
            relations=[
                RelationDTO(
                    source_id=source_id,
                    subject_id=1,
                    predicate="validates_with",
                    object_id=2,
                    confidence=0.88,
                ),
            ],
        )
        report_dto = validate_delta(
            delta_dto=delta_dto,
            source_content=source_text,
            minimum_confidence=0.65,
            repository=self.repository,
        )

        self.assertTrue(report_dto.valid)
        apply_validated_delta(
            repository=self.repository,
            source_id=source_id,
            delta_dto=report_dto.accepted_delta,
            source_content=source_text,
        )

        with self.repository.session() as connection:
            entity_class_row = connection.execute(
                "SELECT name FROM entity_classes WHERE name = ?",
                ("Evaluator",),
            ).fetchone()
            relation_type_row = connection.execute(
                "SELECT name FROM relation_types WHERE name = ?",
                ("validates_with",),
            ).fetchone()

        self.assertIsNotNone(entity_class_row)
        self.assertIsNotNone(relation_type_row)

    def test_validation_reviews_cls_before_dependent_entities(self) -> None:
        """Ensure same-delta CLS entities validate objects even when they arrive later."""
        source_id = self._default_source_id()
        delta_dto = KnowledgeDeltaDTO(
            source_path="memory/default.md",
            entities=[
                EntityDTO(
                    id=1,
                    source_id=source_id,
                    entity_class="PRODUCT.ExtractedPrompt",
                    canonical_name="Prompt Template",
                    confidence=0.9,
                ),
                EntityDTO(
                    id=2,
                    source_id=source_id,
                    entity_class="CLS",
                    canonical_name="ExtractedPrompt",
                    description="Reusable class for a prompt template detected from text.",
                    confidence=0.9,
                ),
            ],
        )

        report_dto = validate_delta(
            delta_dto=delta_dto,
            source_content="Prompt Template is a reusable prompt file.",
            minimum_confidence=0.65,
            repository=self.repository,
        )

        self.assertTrue(report_dto.valid)
        self.assertEqual(report_dto.accepted_delta.entities[0].entity_class, "CLS")
        self.assertEqual(report_dto.accepted_delta.entities[1].entity_class, "PRODUCT.ExtractedPrompt")
        self.assertNotIn("without CLS class definition", " ".join(report_dto.warnings))

    def test_query_and_export_jsonld(self) -> None:
        """Ensure applied entities are searchable and exportable."""
        entity_id = self.repository.upsert_entity(
            EntityDTO(
                source_id=self._default_source_id(),
                entity_class="MISC.ConsolidatedClaim",
                canonical_name="Knowledge graph stores evidence",
                description="SQLite FTS should find this evidence store concept.",
                confidence=0.8,
            ),
        )

        results = self.repository.search(text="evidence store", limit=5)
        exported = export_jsonld(repository=self.repository)

        self.assertEqual(entity_id, self.repository.get_entity("Knowledge graph stores evidence")["id"])
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("@graph", exported)

    def test_validation_accepts_compact_windows_artifact_paths(self) -> None:
        """Ensure Windows paths are treated as technical labels, not prose."""
        source_id = self._default_source_id()
        report_dto = validate_delta(
            delta_dto=KnowledgeDeltaDTO(
                source_path="memory/default.md",
                entities=[
                    EntityDTO(
                        id=1,
                        source_id=source_id,
                        entity_class="FILE",
                        canonical_name="D:\\.agents\\@Angi\\.tmp",
                        description="Temporary workspace path.",
                        confidence=0.9,
                    ),
                ],
            ),
            source_content="D:\\.agents\\@Angi\\.tmp stores temporary work.",
            minimum_confidence=0.65,
            repository=self.repository,
        )

        self.assertTrue(report_dto.valid)
        self.assertEqual(len(report_dto.accepted_delta.entities), 1)

    def test_repository_reuses_stable_entity_name_with_source_type_assertions(self) -> None:
        """Ensure class changes add assertions without duplicating the entity."""
        first_source_id = self._default_source_id()
        second_source_id = self.repository.upsert_source(
            SourceDTO(source_type="memory", path="memory/second.md", title="second"),
        )

        first_entity_id = self.repository.upsert_entity(
            EntityDTO(
                source_id=first_source_id,
                entity_class="PERSON",
                canonical_name="Angi",
                description="Named participant in the source.",
                confidence=0.88,
            ),
        )
        second_entity_id = self.repository.upsert_entity(
            EntityDTO(
                source_id=second_source_id,
                entity_class="MISC.DigitalPet",
                canonical_name="Angi",
                description="Digital companion interpretation in another source.",
                confidence=0.91,
            ),
        )

        assertions = self.repository.list_entity_type_assertions(entity_id=first_entity_id)
        assertion_classes = {str(assertion["entity_class"]) for assertion in assertions}

        self.assertEqual(first_entity_id, second_entity_id)
        self.assertEqual(self.repository.status()["counts"]["entities"], 1)
        self.assertIn("PERSON", assertion_classes)
        self.assertIn("MISC.DigitalPet", assertion_classes)
        self.assertEqual(
            self.repository.get_entity("Angi")["id"],
            first_entity_id,
        )

    def test_schema_migration_merges_existing_entities_by_normalized_name(self) -> None:
        """Ensure old class-keyed duplicates migrate into stable entities."""
        db_path = self.root / "legacy_knowledge.db"
        connection = sqlite3.connect(str(db_path))
        try:
            connection.executescript(
                """
                CREATE TABLE sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    path TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id INTEGER,
                    entity_class TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0.65,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    merged_into_id INTEGER,
                    UNIQUE(entity_class, normalized_name)
                );

                CREATE TABLE relation_types (
                    name TEXT PRIMARY KEY,
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at REAL NOT NULL
                );

                CREATE TABLE relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id INTEGER NOT NULL,
                    subject_entity_id INTEGER NOT NULL,
                    predicate TEXT NOT NULL,
                    object_entity_id INTEGER NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.65,
                    UNIQUE(source_id, subject_entity_id, predicate, object_entity_id)
                );
                """
            )
            connection.executemany(
                "INSERT INTO sources(id, source_type, path, title, active) VALUES(?, ?, ?, ?, ?)",
                (
                    (1, "memory", "memory/a.md", "a", 1),
                    (2, "memory", "memory/b.md", "b", 1),
                ),
            )
            connection.executemany(
                """
                INSERT INTO entities(
                    id,
                    source_id,
                    entity_class,
                    canonical_name,
                    normalized_name,
                    description,
                    confidence,
                    status,
                    created_at,
                    updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (1, 1, "PERSON", "Angi", "angi", "Person interpretation.", 0.82, "active", 1.0, 1.0),
                    (
                        2,
                        2,
                        "MISC.DigitalPet",
                        "Angi",
                        "angi",
                        "Companion interpretation.",
                        0.91,
                        "active",
                        1.0,
                        1.0,
                    ),
                    (3, 2, "MISC.Concept", "Knowledge", "knowledge", "Object node.", 0.7, "active", 1.0, 1.0),
                ),
            )
            connection.execute(
                "INSERT INTO relation_types(name, description, status, created_at) VALUES(?, ?, ?, ?)",
                ("describes", "test", "active", 1.0),
            )
            connection.execute(
                """
                INSERT INTO relations(source_id, subject_entity_id, predicate, object_entity_id, confidence)
                VALUES(?, ?, ?, ?, ?)
                """,
                (2, 2, "describes", 3, 0.9),
            )
            connection.commit()
        finally:
            connection.close()

        migrated_repository = KnowledgeRepository(db_path=db_path)
        angi_row = migrated_repository.get_entity("Angi")
        assertions = migrated_repository.list_entity_type_assertions(entity_id=int(angi_row["id"]))

        with migrated_repository.session() as migrated_connection:
            active_duplicates = migrated_connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM entities
                WHERE normalized_name = 'angi' AND status != 'merged'
                """,
            ).fetchone()
            merged_rows = migrated_connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM entities
                WHERE normalized_name = 'angi' AND status = 'merged'
                """,
            ).fetchone()
            relation_row = migrated_connection.execute("SELECT * FROM relations").fetchone()

        self.assertEqual(int(active_duplicates["count"]), 1)
        self.assertEqual(int(merged_rows["count"]), 1)
        self.assertEqual(int(relation_row["subject_entity_id"]), int(angi_row["id"]))
        self.assertEqual(
            {str(assertion["entity_class"]) for assertion in assertions},
            {"PERSON", "MISC.DigitalPet"},
        )

    def test_dream_dry_run_and_apply(self) -> None:
        """Ensure LLM-only dream keeps deltas pending and apply writes entities."""
        memory_dir = self.root / "memory" / "profiles" / "developer"
        memory_dir.mkdir(parents=True)
        source_path = memory_dir / "rules.md"
        source_path.write_text(
            "# Developer Rules\n\nAlways validate evidence before applying deltas.",
            encoding="utf-8",
        )

        def fake_generate_multistage_deltas(
            source_path: str,
            content: str,
            base_delta: KnowledgeDeltaDTO,
            graph_context: str = "",
            entity_name_to_id: dict[str, int] | None = None,
            entity_class_catalog: dict[str, str] | None = None,
            stage_names: tuple[str, ...] = (),
        ) -> tuple[list[tuple[str, KnowledgeDeltaDTO]], list[str]]:
            """Return a compact LLM-style entity delta."""
            del source_path, content, base_delta, graph_context, entity_name_to_id, entity_class_catalog, stage_names
            delta_dto = KnowledgeDeltaDTO(
                entities=[
                    EntityDTO(
                        id=1,
                        entity_class="LAW.PolicyRule",
                        canonical_name="Evidence Validation",
                        description="Validation policy extracted structurally.",
                        confidence=0.9,
                    ),
                    EntityDTO(
                        id=2,
                        entity_class="CLS",
                        canonical_name="PolicyRule",
                        description="Policy-like rule extracted from procedural text.",
                        confidence=0.9,
                    ),
                ],
                rationale="llm stage",
            )
            return [("entity_detection", delta_dto)], []

        original_generate = dream_module.generate_multistage_deltas
        dream_module.generate_multistage_deltas = fake_generate_multistage_deltas
        try:
            runner = DreamRunner(repository=self.repository)
            dry_run_dto = runner.run(domain="profiles", limit=1, dry_run=True, minimum_confidence=0.65)
            apply_dto = runner.run(domain="profiles", limit=1, dry_run=False, minimum_confidence=0.65)
        finally:
            dream_module.generate_multistage_deltas = original_generate

        self.assertEqual(dry_run_dto.deltas_applied, 0)
        self.assertEqual(len(dry_run_dto.pending_delta_ids), 1)
        pending_delta = self.repository.get_pending_delta(delta_id=dry_run_dto.pending_delta_ids[0])
        self.assertIsNotNone(pending_delta)
        self.assertIn("payload", pending_delta)
        self.assertIn("validation", pending_delta)
        self.assertGreaterEqual(len(self.repository.list_pending_deltas(limit=5)), 1)
        rendered_delta = render_delta_review(
            rows=[pending_delta],
            color_enabled=False,
            compact=False,
        )
        rendered_color_delta = render_delta_review(
            rows=[pending_delta],
            color_enabled=True,
            compact=False,
        )
        self.assertIn('why: "LLM-only structural extraction.; llm stage"', rendered_delta)
        self.assertIn("proposed entities", rendered_delta)
        self.assertIn('[LAW.PolicyRule:"Evidence Validation"]', rendered_delta)
        self.assertIn("legend: Et=entities  Re=relations  Ale=aliases  Sch=schema", rendered_delta)
        self.assertIn("proposed: Et 2  Re 0  Ale 0  Sch 0", rendered_delta)
        self.assertIn("accepted: Et 2  Re 0  Ale 0  Sch 0", rendered_delta)
        self.assertIn("errors: 0", rendered_delta)
        self.assertIn("warnings: 0", rendered_delta)
        self.assertNotIn("delta #", rendered_delta)
        self.assertNotIn("canonical_name=", rendered_delta)
        self.assertNotIn("entity_class=", rendered_delta)
        self.assertIn('\033[34m"', rendered_color_delta)
        self.assertEqual(apply_dto.deltas_applied, 0)

        source_path.write_text(
            "# Developer Rules\n\nAlways validate evidence before applying deltas.\nMust keep SQLite private.",
            encoding="utf-8",
        )
        dream_module.generate_multistage_deltas = fake_generate_multistage_deltas
        try:
            apply_dto = runner.run(domain="profiles", limit=1, dry_run=False, minimum_confidence=0.65)
        finally:
            dream_module.generate_multistage_deltas = original_generate
        self.assertGreaterEqual(apply_dto.deltas_applied, 1)
        status_payload = self.repository.status()
        self.assertGreater(status_payload["counts"]["entities"], 0)

    def test_dream_cycle_reuses_cls_declared_by_prior_source(self) -> None:
        """Ensure one dream pass caches accepted CLS entities for later source validation."""
        memory_dir = self.root / "memory" / "profiles" / "developer"
        memory_dir.mkdir(parents=True)
        class_path = memory_dir / "01-class.md"
        object_path = memory_dir / "02-object.md"
        object_path.write_text("# Object\n\nPrompt Contract is used by the extraction harness.", encoding="utf-8")
        class_path.write_text("# Class\n\nKnowledgeContract defines a reusable classifier.", encoding="utf-8")
        os.utime(object_path, (1_000_000, 1_000_000))
        os.utime(class_path, (2_000_000, 2_000_000))

        catalogs_by_source: dict[str, dict[str, str]] = {}

        def fake_generate_multistage_deltas(
            source_path: str,
            content: str,
            base_delta: KnowledgeDeltaDTO,
            graph_context: str = "",
            entity_name_to_id: dict[str, int] | None = None,
            entity_class_catalog: dict[str, str] | None = None,
            stage_names: tuple[str, ...] = (),
        ) -> tuple[list[tuple[str, KnowledgeDeltaDTO]], list[str]]:
            """Return a class delta first, then an object using that class."""
            del content, base_delta, graph_context, entity_name_to_id, stage_names
            catalogs_by_source[source_path] = dict(entity_class_catalog or {})
            if source_path.endswith("01-class.md"):
                return [
                    (
                        "entity_detection",
                        KnowledgeDeltaDTO(
                            entities=[
                                EntityDTO(
                                    id=1,
                                    entity_class="CLS",
                                    canonical_name="KnowledgeContract",
                                    description="Reusable class discovered from source content.",
                                    confidence=0.92,
                                ),
                            ],
                            rationale="class declaration",
                        ),
                    ),
                ], []
            return [
                (
                    "entity_detection",
                    KnowledgeDeltaDTO(
                        entities=[
                            EntityDTO(
                                id=1,
                                entity_class="PRODUCT.KnowledgeContract",
                                canonical_name="Prompt Contract",
                                description="Specific object classified by a prior CLS.",
                                confidence=0.92,
                            ),
                        ],
                        rationale="object declaration",
                    ),
                ),
            ], []

        original_generate = dream_module.generate_multistage_deltas
        dream_module.generate_multistage_deltas = fake_generate_multistage_deltas
        try:
            runner = DreamRunner(repository=self.repository)
            dream_dto = runner.run(domain="profiles", limit=2, dry_run=True, minimum_confidence=0.65)
        finally:
            dream_module.generate_multistage_deltas = original_generate

        self.assertEqual(dream_dto.deltas_proposed, 2)
        self.assertEqual(dream_dto.deltas_applied, 0)
        self.assertIn("KnowledgeContract", catalogs_by_source["memory/profiles/developer/02-object.md"])

        object_delta = self.repository.get_pending_delta(delta_id=dream_dto.pending_delta_ids[1])
        self.assertIsNotNone(object_delta)
        warning_text = " ".join(object_delta["validation"].get("warnings", []))
        accepted_entities = object_delta["validation"]["accepted_delta"].get("entities", [])
        self.assertNotIn("without CLS class definition", warning_text)
        self.assertEqual(accepted_entities[0]["entity_class"], "PRODUCT.KnowledgeContract")

    def test_dream_bootstrap_detects_empty_graph(self) -> None:
        """Ensure dream can identify an empty graph that needs first-run population."""
        self.assertTrue(is_bootstrap_required(repository=self.repository))

        self.repository.upsert_entity(
            EntityDTO(
                source_id=self._default_source_id(),
                entity_class="MISC.Concept",
                canonical_name="Seed Entity",
                description="A seeded graph entity.",
                confidence=0.9,
            ),
        )

        self.assertFalse(is_bootstrap_required(repository=self.repository))

    def test_dream_scope_plan_defaults_to_global_and_local(self) -> None:
        """Ensure dream uses scope selectors rather than domain selectors for graph isolation."""
        self.assertEqual(
            resolve_dream_scope_plan(scope="all", domain="all"),
            [{"scope": "global", "domain": "all"}, {"scope": "local", "domain": "logs"}],
        )
        self.assertEqual(
            resolve_dream_scope_plan(scope="global", domain="all"),
            [{"scope": "global", "domain": "all"}],
        )
        self.assertEqual(
            resolve_dream_scope_plan(scope="local", domain="all"),
            [{"scope": "local", "domain": "all"}],
        )

    def test_dream_json_mode_does_not_bootstrap_apply(self) -> None:
        """Ensure JSON dream output proposes but does not mutate an empty graph."""
        memory_dir = self.root / "memory" / "profiles" / "developer"
        memory_dir.mkdir(parents=True)
        source_path = memory_dir / "bootstrap.md"
        source_path.write_text("# Bootstrap\n\nBootstrap Node defines a first graph object.", encoding="utf-8")

        def fake_generate_multistage_deltas(
            source_path: str,
            content: str,
            base_delta: KnowledgeDeltaDTO,
            graph_context: str = "",
            entity_name_to_id: dict[str, int] | None = None,
            entity_class_catalog: dict[str, str] | None = None,
            stage_names: tuple[str, ...] = (),
        ) -> tuple[list[tuple[str, KnowledgeDeltaDTO]], list[str]]:
            """Return one valid first-population delta."""
            del source_path, content, base_delta, graph_context, entity_name_to_id, entity_class_catalog, stage_names
            return [
                (
                    "entity_detection",
                    KnowledgeDeltaDTO(
                        entities=[
                            EntityDTO(
                                id=1,
                                entity_class="CLS",
                                canonical_name="BootstrapThing",
                                description="First-population class definition.",
                                confidence=0.9,
                            ),
                            EntityDTO(
                                id=2,
                                entity_class="PRODUCT.BootstrapThing",
                                canonical_name="Bootstrap Node",
                                description="First-population graph object.",
                                confidence=0.9,
                            ),
                        ],
                        rationale="bootstrap proposal",
                    ),
                ),
            ], []

        original_generate = dream_module.generate_multistage_deltas
        dream_module.generate_multistage_deltas = fake_generate_multistage_deltas
        args = argparse.Namespace(
            color=False,
            domain="profiles",
            json=True,
            limit=1,
            llm=True,
            min_confidence=0.65,
            prune=False,
            scope="global",
            verbose_log=False,
        )
        try:
            with redirect_stdout(io.StringIO()) as stdout:
                status_code = command_dream_module.handle(args)
        finally:
            dream_module.generate_multistage_deltas = original_generate

        stdout_text: str = stdout.getvalue()
        payload = json.loads(stdout_text[stdout_text.find("{"):])
        self.assertEqual(status_code, 0)
        self.assertTrue(payload["bootstrap_required"])
        self.assertFalse(payload["bootstrap_allowed"])
        self.assertEqual(payload["bootstrap_applied"], 0)
        self.assertEqual(self.repository.status()["counts"]["entities"], 0)
        self.assertGreaterEqual(len(self.repository.list_pending_deltas(limit=5)), 1)

    def test_dream_blocks_when_pending_delta_buffer_exists(self) -> None:
        """Ensure dream refuses a new cycle while pending deltas remain unresolved."""
        source_id = self._default_source_id()
        delta_id = self.repository.record_pending_delta(
            source_id=source_id,
            payload=KnowledgeDeltaDTO(source_path="memory/default.md").model_dump(mode="json"),
            validation={
                "valid": False,
                "errors": ["test"],
                "warnings": [],
                "accepted_delta": KnowledgeDeltaDTO(source_path="memory/default.md").model_dump(mode="json"),
            },
        )
        args = argparse.Namespace(
            color=False,
            domain="profiles",
            json=True,
            limit=1,
            llm=True,
            min_confidence=0.65,
            prune=False,
            scope="global",
            verbose_log=False,
        )

        with redirect_stdout(io.StringIO()) as stdout:
            status_code = command_dream_module.handle(args)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(status_code, 2)
        self.assertTrue(payload["blocked"])
        self.assertEqual(payload["reason"], "pending_delta_buffer_not_empty")
        self.assertEqual(payload["delta_status"]["pending"], 1)
        self.assertEqual(payload["pending_deltas"][0]["id"], delta_id)
        self.assertIn("knowledge-deltas", payload["helper"]["apply"])
        self.assertIn("delete-knowledge-deltas", payload["helper"]["delete"])

    def test_dream_verbose_logs_bootstrap_application_steps(self) -> None:
        """Ensure verbose dream output includes step-by-step delta application events."""
        memory_dir = self.root / "memory" / "profiles" / "developer"
        memory_dir.mkdir(parents=True)
        source_path = memory_dir / "bootstrap.md"
        source_path.write_text("# Bootstrap\n\nBootstrap Node defines a first graph object.", encoding="utf-8")

        def fake_generate_multistage_deltas(
            source_path: str,
            content: str,
            base_delta: KnowledgeDeltaDTO,
            graph_context: str = "",
            entity_name_to_id: dict[str, int] | None = None,
            entity_class_catalog: dict[str, str] | None = None,
            stage_names: tuple[str, ...] = (),
            event_callback: object | None = None,
        ) -> tuple[list[tuple[str, KnowledgeDeltaDTO]], list[str]]:
            """Return one valid bootstrap delta."""
            del source_path, content, base_delta, graph_context, entity_name_to_id
            del entity_class_catalog, stage_names, event_callback
            return [
                (
                    "entity_detection",
                    KnowledgeDeltaDTO(
                        entities=[
                            EntityDTO(
                                id=1,
                                entity_class="CLS",
                                canonical_name="BootstrapThing",
                                description="First-population class definition.",
                                confidence=0.9,
                            ),
                            EntityDTO(
                                id=2,
                                entity_class="PRODUCT.BootstrapThing",
                                canonical_name="Bootstrap Node",
                                description="First-population graph object.",
                                confidence=0.9,
                            ),
                        ],
                        rationale="bootstrap proposal",
                    ),
                ),
            ], []

        original_generate = dream_module.generate_multistage_deltas
        dream_module.generate_multistage_deltas = fake_generate_multistage_deltas
        args = argparse.Namespace(
            color=False,
            domain="profiles",
            json=False,
            limit=1,
            llm=True,
            min_confidence=0.65,
            prune=False,
            scope="global",
            verbose_log=True,
        )
        try:
            with redirect_stdout(io.StringIO()) as stdout:
                status_code = command_dream_module.handle(args)
        finally:
            dream_module.generate_multistage_deltas = original_generate

        output_text = stdout.getvalue()
        self.assertEqual(status_code, 0)
        self.assertIn("[dream:run]", output_text)
        self.assertIn("[dream:source]", output_text)
        self.assertIn("memory/profiles/developer/bootstrap.md", output_text)
        self.assertIn("[apply:start]", output_text)
        self.assertIn("[apply:validate]", output_text)
        self.assertIn("[apply:write]", output_text)
        self.assertIn("[apply:complete]", output_text)
        self.assertGreater(self.repository.status()["counts"]["entities"], 0)

    def test_dream_selection_parser_supports_all_none_and_subsets(self) -> None:
        """Ensure dream confirmation accepts y/n and comma-separated delta IDs."""
        applicable_delta_ids = {48, 52, 61}

        self.assertEqual(parse_delta_selection("y", applicable_delta_ids), {48, 52, 61})
        self.assertEqual(parse_delta_selection("n", applicable_delta_ids), set())
        self.assertEqual(parse_delta_selection("48,61", applicable_delta_ids), {48, 61})

        with self.assertRaises(ValueError):
            parse_delta_selection("50", applicable_delta_ids)

    def test_dream_llm_diagnostics_require_verbose_log(self) -> None:
        """Ensure dream only streams LLM call diagnostics when explicitly verbose."""
        quiet_args = argparse.Namespace(json=False, verbose_log=False)
        verbose_args = argparse.Namespace(json=False, verbose_log=True)
        json_args = argparse.Namespace(json=True, verbose_log=True)

        self.assertIsNone(resolve_llm_event_callback(args=quiet_args, color_enabled=False))
        self.assertIsNotNone(resolve_llm_event_callback(args=verbose_args, color_enabled=False))
        self.assertIsNone(resolve_llm_event_callback(args=json_args, color_enabled=False))
        self.assertIsNone(resolve_application_event_callback(args=quiet_args, color_enabled=False))
        self.assertIsNotNone(resolve_application_event_callback(args=verbose_args, color_enabled=False))
        self.assertIsNone(resolve_application_event_callback(args=json_args, color_enabled=False))
        self.assertIsNone(resolve_orchestration_event_callback(args=quiet_args, color_enabled=False))
        self.assertIsNotNone(resolve_orchestration_event_callback(args=verbose_args, color_enabled=False))
        self.assertIsNone(resolve_orchestration_event_callback(args=json_args, color_enabled=False))

    def test_repository_deletes_pending_deltas_by_id(self) -> None:
        """Ensure unwanted pending delta rows can be deleted safely."""
        source_id = self._default_source_id()
        delta_payload = KnowledgeDeltaDTO(source_path="memory/default.md").model_dump(mode="json")
        validation_payload = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "accepted_delta": KnowledgeDeltaDTO(source_path="memory/default.md").model_dump(mode="json"),
        }
        first_delta_id = self.repository.record_pending_delta(
            source_id=source_id,
            payload=delta_payload,
            validation=validation_payload,
        )
        second_delta_id = self.repository.record_pending_delta(
            source_id=source_id,
            payload=delta_payload,
            validation=validation_payload,
        )

        deleted_count = self.repository.delete_pending_deltas(delta_ids=[first_delta_id])

        self.assertEqual(deleted_count, 1)
        self.assertIsNone(self.repository.get_pending_delta(delta_id=first_delta_id))
        self.assertIsNotNone(self.repository.get_pending_delta(delta_id=second_delta_id))

    def test_delete_knowledge_deltas_all_selects_all_review_rows(self) -> None:
        """Ensure delete-knowledge-deltas --all selects all inspected rows."""
        source_id = self._default_source_id()
        delta_payload = KnowledgeDeltaDTO(source_path="memory/default.md").model_dump(mode="json")
        validation_payload = {
            "valid": False,
            "errors": ["test"],
            "warnings": [],
            "accepted_delta": KnowledgeDeltaDTO(source_path="memory/default.md").model_dump(mode="json"),
        }
        first_delta_id = self.repository.record_pending_delta(
            source_id=source_id,
            payload=delta_payload,
            validation=validation_payload,
        )
        second_delta_id = self.repository.record_pending_delta(
            source_id=source_id,
            payload=delta_payload,
            validation=validation_payload,
        )
        self.repository.update_pending_delta_status(delta_id=second_delta_id, status="failed")
        args = argparse.Namespace(ids=[], all=True, legacy=False, status=None, limit=10)

        rows = _select_candidate_rows(repository=self.repository, args=args)

        self.assertEqual({int(row["id"]) for row in rows}, {first_delta_id, second_delta_id})

    def test_delete_knowledge_deltas_json_requires_yes_without_prompting(self) -> None:
        """Ensure delete JSON mode is non-interactive unless --yes is explicit."""
        self.assertFalse(_confirm_deletion(args=argparse.Namespace(yes=False, json=True), candidate_ids=[1]))
        self.assertTrue(_confirm_deletion(args=argparse.Namespace(yes=True, json=True), candidate_ids=[1]))

    def test_knowledge_deltas_apply_persists_selected_delta(self) -> None:
        """Ensure knowledge-deltas can apply selected pending proposals."""
        source_id = self._default_source_id()
        delta_dto = KnowledgeDeltaDTO(
            source_path="memory/default.md",
            entities=[
                EntityDTO(
                    id=1,
                    source_id=source_id,
                    entity_class="PERSON.Reviewer",
                    canonical_name="Reviewer",
                    confidence=0.9,
                ),
                EntityDTO(
                    id=2,
                    source_id=source_id,
                    entity_class="PRODUCT.SoftwareArtifact",
                    canonical_name="BuildArtifact",
                    confidence=0.9,
                ),
                EntityDTO(
                    id=3,
                    source_id=source_id,
                    entity_class="CLS",
                    canonical_name="Reviewer",
                    description="Actor that reviews or audits another graph object.",
                    confidence=0.9,
                ),
                EntityDTO(
                    id=4,
                    source_id=source_id,
                    entity_class="CLS",
                    canonical_name="SoftwareArtifact",
                    description="Concrete software output, package, script, or build artifact.",
                    confidence=0.9,
                ),
            ],
            relations=[
                RelationDTO(
                    source_id=source_id,
                    subject_id=1,
                    predicate="audits",
                    object_id=2,
                    confidence=0.9,
                ),
            ],
        )
        delta_id = self.repository.record_pending_delta(
            source_id=source_id,
            payload=delta_dto.model_dump(mode="json"),
            validation={
                "valid": True,
                "errors": [],
                "warnings": [],
                "accepted_delta": delta_dto.model_dump(mode="json"),
            },
        )
        args = argparse.Namespace(
            color=False,
            id=delta_id,
            json=True,
            limit=10,
            scope="global",
            status="pending",
            yes=True,
        )
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            status_code = command_knowledge_deltas_module.handle(args)

        self.assertEqual(parse_delta_selection("y", {delta_id}), {delta_id})
        self.assertEqual(parse_delta_selection(str(delta_id), {delta_id}), {delta_id})
        self.assertEqual(status_code, 0)
        self.assertIsNotNone(self.repository.get_entity("Reviewer"))
        self.assertEqual(self.repository.get_pending_delta(delta_id=delta_id)["status"], "applied")

    def test_knowledge_deltas_apply_uses_payload_as_source_of_truth(self) -> None:
        """Ensure stale validation cache cannot suppress a valid raw delta."""
        source_id = self._default_source_id()
        delta_dto = KnowledgeDeltaDTO(
            source_path="memory/default.md",
            entities=[
                EntityDTO(
                    id=1,
                    source_id=source_id,
                    entity_class="FILE",
                    canonical_name="README.md",
                    description="Repository readme file.",
                    confidence=0.9,
                ),
            ],
        )
        delta_id = self.repository.record_pending_delta(
            source_id=source_id,
            payload=delta_dto.model_dump(mode="json"),
            validation={
                "valid": False,
                "errors": ["stale cache"],
                "warnings": [],
                "accepted_delta": KnowledgeDeltaDTO(source_path="memory/default.md").model_dump(mode="json"),
            },
        )
        args = argparse.Namespace(
            color=False,
            id=delta_id,
            json=True,
            limit=10,
            scope="global",
            status="pending",
            yes=True,
        )

        with redirect_stdout(io.StringIO()):
            status_code = command_knowledge_deltas_module.handle(args)

        refreshed_delta = self.repository.get_pending_delta(delta_id=delta_id)
        self.assertEqual(status_code, 0)
        self.assertIsNotNone(self.repository.get_entity("README.md"))
        self.assertEqual(refreshed_delta["status"], "applied")
        self.assertTrue(refreshed_delta["validation"]["valid"])

    def test_knowledge_deltas_apply_revalidates_missing_cls_definitions(self) -> None:
        """Ensure old accepted deltas cannot apply without required CLS entities."""
        source_id = self._default_source_id()
        delta_dto = KnowledgeDeltaDTO(
            source_path="memory/default.md",
            entities=[
                EntityDTO(
                    id=1,
                    source_id=source_id,
                    entity_class="legacy_class",
                    canonical_name="LegacyClass",
                    confidence=0.9,
                ),
            ],
        )
        delta_id = self.repository.record_pending_delta(
            source_id=source_id,
            payload=delta_dto.model_dump(mode="json"),
            validation={
                "valid": True,
                "errors": [],
                "warnings": [],
                "accepted_delta": delta_dto.model_dump(mode="json"),
            },
        )
        args = argparse.Namespace(
            color=False,
            id=delta_id,
            json=True,
            limit=10,
            scope="global",
            status="pending",
            yes=True,
        )

        with redirect_stdout(io.StringIO()):
            status_code = command_knowledge_deltas_module.handle(args)

        self.assertEqual(status_code, 0)
        self.assertIsNone(self.repository.get_entity("LegacyClass"))
        refreshed_delta = self.repository.get_pending_delta(delta_id=delta_id)
        self.assertEqual(refreshed_delta["status"], "pending")
        self.assertFalse(refreshed_delta["validation"]["valid"])

    def test_delta_cli_renderer_shows_entities_and_relations(self) -> None:
        """Ensure CLI delta review prints proposed entities and relations."""
        delta_dto = KnowledgeDeltaDTO(
            source_path="memory/notes/review.md",
            entities=[
                EntityDTO(
                    id=1,
                    source_id=10,
                    entity_class="PERSON.Reviewer",
                    canonical_name="Reviewer",
                    confidence=0.91,
                ),
                EntityDTO(
                    id=2,
                    source_id=10,
                    entity_class="PRODUCT.SoftwareArtifact",
                    canonical_name="BuildArtifact",
                    confidence=0.9,
                ),
            ],
            relations=[
                RelationDTO(
                    source_id=10,
                    subject_id=1,
                    predicate="audits",
                    object_id=2,
                    confidence=0.9,
                ),
            ],
            rationale="Renderer contract fixture.",
        )
        row = {
            "id": 41,
            "source_path": delta_dto.source_path,
            "payload": delta_dto.model_dump(mode="json"),
            "validation": {
                "valid": True,
                "errors": [],
                "warnings": [],
                "accepted_delta": delta_dto.model_dump(mode="json"),
            },
        }

        rendered_delta = render_delta_review(rows=[row], color_enabled=False, compact=False)

        self.assertIn("[41] applicable", rendered_delta)
        self.assertIn("proposed entities", rendered_delta)
        self.assertIn('[PERSON.Reviewer:"Reviewer"]', rendered_delta)
        self.assertIn('dc: ""', rendered_delta)
        self.assertIn("src: 10", rendered_delta)
        self.assertIn("c: .91", rendered_delta)
        self.assertNotIn("proposed aliases", rendered_delta)
        self.assertIn("proposed relations", rendered_delta)
        self.assertIn(
            '[PERSON.Reviewer:"Reviewer"] - ("audits" at .90) -> [PRODUCT.SoftwareArtifact:"BuildArtifact"]',
            rendered_delta,
        )
        self.assertIn("legend: Et=entities  Re=relations  Ale=aliases  Sch=schema", rendered_delta)
        self.assertIn("proposed: Et 2  Re 1  Ale 0  Sch 0", rendered_delta)
        self.assertIn("accepted: Et 2  Re 1  Ale 0  Sch 0", rendered_delta)
        self.assertNotIn("Et2", rendered_delta)
        self.assertNotIn("Re1", rendered_delta)
        self.assertNotIn("Ale1", rendered_delta)
        self.assertNotIn("Sch0", rendered_delta)
        self.assertNotIn("E2", rendered_delta)
        self.assertNotIn("A0", rendered_delta)
        self.assertNotIn("R1", rendered_delta)
        self.assertNotIn("S0", rendered_delta)
        self.assertNotIn("delta #", rendered_delta)
        self.assertNotIn("db#", rendered_delta)
        self.assertNotIn("src#", rendered_delta)
        self.assertNotIn("c1.00", rendered_delta)

    def test_delta_cli_renderer_hides_legacy_contract_payloads(self) -> None:
        """Ensure legacy deltas do not render retired heuristic objects."""
        row = {
            "id": 7,
            "source_path": "memory/legacy.md",
            "payload": {
                "source_path": "memory/legacy.md",
                "entities": [
                    {
                        "entity_class": "source_document",
                        "canonical_name": "Always validate evidence before applying deltas",
                        "confidence": 0.74,
                    },
                ],
                "relations": [
                    {
                        "subject_ref": "Legacy",
                        "predicate": "derived_from",
                        "object_value": "memory/legacy.md",
                        "confidence": 0.7,
                    },
                ],
                "schema_suggestions": [],
                "aliases": [],
                "rationale": "Deterministic fallback extraction from source metadata.",
            },
            "validation": {
                "valid": True,
                "errors": [],
                "warnings": [],
                "accepted_delta": {"entities": [], "relations": [], "aliases": [], "schema_suggestions": []},
            },
        }

        rendered_delta = render_delta_review(rows=[row], color_enabled=False, compact=False)

        self.assertIn("legacy contract hidden", rendered_delta)
        self.assertNotIn("Always validate evidence", rendered_delta)
        self.assertNotIn("derived_from", rendered_delta)

    def test_delta_cli_renderer_shows_current_invalid_relation_payloads(self) -> None:
        """Ensure current deltas with rejected relations are still reviewable."""
        source_id = self._default_source_id()
        row = {
            "id": 89,
            "source_path": "memory/current.md",
            "payload": KnowledgeDeltaDTO(
                source_path="memory/current.md",
                entities=[
                    EntityDTO(
                        id=1_000_000_001,
                        source_id=source_id,
                        entity_class="PERSON.Reviewer",
                        canonical_name="Reviewer",
                        confidence=0.9,
                    ),
                ],
                relations=[
                    RelationDTO(
                        source_id=source_id,
                        subject_id=None,
                        object_id=None,
                        predicate="audits",
                        confidence=0.9,
                    ),
                ],
            ).model_dump(mode="json"),
            "validation": {
                "valid": True,
                "errors": [],
                "warnings": ["Rejected relation `audits` without subject_id."],
                "accepted_delta": KnowledgeDeltaDTO(
                    source_path="memory/current.md",
                    entities=[
                        EntityDTO(
                            id=1_000_000_001,
                            source_id=source_id,
                            entity_class="PERSON.Reviewer",
                            canonical_name="Reviewer",
                            confidence=0.9,
                        ),
                    ],
                ).model_dump(mode="json"),
            },
        }

        rendered_delta = render_delta_review(rows=[row], color_enabled=False, compact=False)

        self.assertNotIn("legacy contract hidden", rendered_delta)
        self.assertIn("proposed entities", rendered_delta)
        self.assertIn("proposed relations", rendered_delta)
        self.assertIn('[PERSON.Reviewer:"Reviewer"]', rendered_delta)

    def test_cli_json_payload_shape(self) -> None:
        """Ensure JSON serialization handles exported payloads."""
        payload = export_jsonld(repository=self.repository)
        encoded_payload = json.dumps(payload, ensure_ascii=False)
        self.assertIn("@context", encoded_payload)

    def test_dream_llm_runs_minimal_structural_stages(self) -> None:
        """Ensure dream consumes only entity and relation LLM stage deltas."""
        memory_dir = self.root / "memory" / "diary" / "2026-07"
        memory_dir.mkdir(parents=True)
        source_path = memory_dir / "03-07-2026.md"
        source_text = "# Day\n\nReviewer audits BuildArtifact. Always keep SQLite private."
        source_path.write_text(source_text, encoding="utf-8")

        calls: list[str] = []

        def fake_generate_multistage_deltas(
            source_path: str,
            content: str,
            base_delta: KnowledgeDeltaDTO,
            graph_context: str = "",
            entity_name_to_id: dict[str, int] | None = None,
            entity_class_catalog: dict[str, str] | None = None,
            stage_names: tuple[str, ...] = (),
        ) -> tuple[list[tuple[str, KnowledgeDeltaDTO]], list[str]]:
            """Return one valid delta for every configured stage."""
            del source_path, content, base_delta, graph_context, entity_name_to_id, entity_class_catalog
            results: list[tuple[str, KnowledgeDeltaDTO]] = []
            configured_stages = stage_names or (
                "entity_detection",
                "relation_extraction",
            )
            for stage_name in configured_stages:
                calls.append(stage_name)
                results.append((stage_name, _stage_delta(stage_name=stage_name)))
            return results, []

        original_generate = dream_module.generate_multistage_deltas
        dream_module.generate_multistage_deltas = fake_generate_multistage_deltas
        try:
            runner = DreamRunner(repository=self.repository)
            dream_dto = runner.run(
                domain="diary",
                limit=1,
                dry_run=False,
                use_llm=True,
                minimum_confidence=0.65,
            )
        finally:
            dream_module.generate_multistage_deltas = original_generate

        self.assertEqual(
            calls,
            [
                "entity_detection",
                "relation_extraction",
            ],
        )
        self.assertEqual(dream_dto.deltas_applied, 1)
        self.assertIsNotNone(self.repository.get_entity("Reviewer"))
        self.assertIsNotNone(self.repository.get_entity("BuildArtifact"))
        self.assertGreaterEqual(self.repository.status()["counts"]["relations"], 1)
        with self.repository.session() as connection:
            schema_row = connection.execute(
                "SELECT name FROM relation_types WHERE name = ?",
                ("protects_private_runtime",),
            ).fetchone()
        self.assertIsNone(schema_row)

    def test_knowledge_show_without_entity_prints_overview(self) -> None:
        """Ensure `knowledge-show` no longer requires an entity argument."""
        args = argparse.Namespace(
            entity=None,
            entities=False,
            relations=False,
            classes=False,
            filter=None,
            scope="global",
            json=False,
            color=False,
            verbose_log=False,
        )

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = command_knowledge_show_module.handle(args)

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("# Knowledge Graph Show", output)
        self.assertIn("Use `--entities`, `--relations`, `--classes`", output)

    def test_knowledge_show_lists_filtered_graph_records(self) -> None:
        """Ensure `knowledge-show` can list entities, relations, and classes."""
        source_id = self._default_source_id()
        self.repository.upsert_entity(
            EntityDTO(
                source_id=source_id,
                entity_class="CLS",
                canonical_name="MarkdownDoc",
                description="Markdown document class.",
                confidence=0.95,
            ),
        )
        readme_id = self.repository.upsert_entity(
            EntityDTO(
                source_id=source_id,
                entity_class="FILE.MarkdownDoc",
                canonical_name="README.md",
                description="Repository overview document.",
                confidence=0.9,
            ),
        )
        rule_id = self.repository.upsert_entity(
            EntityDTO(
                source_id=source_id,
                entity_class="RULE.SafetyPolicy",
                canonical_name="Safety Policy",
                description="Operational safety policy.",
                confidence=0.9,
            ),
        )
        self.repository.upsert_relation(
            RelationDTO(
                source_id=source_id,
                subject_id=readme_id,
                predicate="documents",
                object_id=rule_id,
                confidence=0.88,
            ),
        )
        args = argparse.Namespace(
            entity=None,
            entities=True,
            relations=True,
            classes=True,
            filter="Markdown",
            scope="global",
            json=False,
            color=False,
            verbose_log=False,
        )

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = command_knowledge_show_module.handle(args)

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn('[FILE.MarkdownDoc:"README.md"]', output)
        self.assertIn('("documents" at .88)', output)
        self.assertIn("[MarkdownDoc] status: active", output)

def _stage_delta(stage_name: str) -> KnowledgeDeltaDTO:
    """
    Build a valid stage-specific delta for LLM orchestration tests.

    Args:
        stage_name (str): Stage name being simulated.

    Returns:
        KnowledgeDeltaDTO: Stage-specific test delta.
    """
    if stage_name == "entity_detection":
        return KnowledgeDeltaDTO(
            entities=[
                EntityDTO(id=1, entity_class="PERSON.Reviewer", canonical_name="Reviewer", confidence=0.91),
                EntityDTO(
                    id=2,
                    entity_class="PRODUCT.SoftwareArtifact",
                    canonical_name="BuildArtifact",
                    confidence=0.91,
                ),
                EntityDTO(
                    id=3,
                    entity_class="CLS",
                    canonical_name="SoftwareArtifact",
                    description="Software artifact entity subtype.",
                    confidence=0.9,
                ),
                EntityDTO(
                    id=4,
                    entity_class="CLS",
                    canonical_name="Reviewer",
                    description="Actor that reviews or audits another graph object.",
                    confidence=0.9,
                ),
            ],
            rationale="entity stage",
        )
    if stage_name == "relation_extraction":
        return KnowledgeDeltaDTO(
            relations=[
                RelationDTO(
                    subject_id=1,
                    predicate="audits",
                    object_id=2,
                    confidence=0.88,
                ),
            ],
            rationale="relation stage",
        )
    if stage_name == "schema_evolution":
        return KnowledgeDeltaDTO(
            schema_suggestions=[
                SchemaSuggestionDTO(
                    suggestion_type="relation_type",
                    name="protects_private_runtime",
                    description="Runtime storage privacy relation.",
                    confidence=0.72,
                ),
            ],
            rationale="schema stage",
        )
    if stage_name == "deduplication":
        return KnowledgeDeltaDTO(rationale="dedupe stage")
    if stage_name == "consolidation":
        return KnowledgeDeltaDTO(
            entities=[
                EntityDTO(
                    entity_class="MISC.ConsolidatedClaim",
                    canonical_name="SQLite private runtime rule",
                    description="Always keep SQLite private.",
                    confidence=0.77,
                ),
            ],
            rationale="consolidation stage",
        )
    return KnowledgeDeltaDTO(
        entities=[
            EntityDTO(
                entity_class="LAW.RuntimePolicy",
                canonical_name="Runtime policy synthesis",
                description="The agent maintains a private knowledge graph.",
                confidence=0.74,
            ),
        ],
        rationale="profile synthesis stage",
    )


if __name__ == "__main__":
    unittest.main()
