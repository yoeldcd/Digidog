"""Tests for the global brain query service."""

from __future__ import annotations

# Standard Libraries Imports
from datetime import datetime, timezone
import io
import json
import os
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
from brain.presentation.actions.general import command_query as command_query_module
from brain.presentation.views.help.rendering import get_command_help_text, get_short_help_text
from brain.presentation.views.query.results import print_human_deep_response
from brain.application.knowledge.models.dtos.graph import EntityDTO, RelationDTO
from brain.application.knowledge.models.dtos.sources import SourceDTO
from brain.application.querying.context import build_query_context
from brain.application.querying.dtos import GlobalQueryResultDTO, QueryContentDTO
from brain.application.querying.entity_selection import select_deep_entities
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.application.querying.source_refs import source_ref_from_path
from brain.application.querying.text_mapping import build_memory_text_result
from brain.application.querying.service import query_deep, query_global


class FakeVectorStoreManager:
    """
    Test double for memory vectorstore queries.

    Attributes:
        db_path: Optional vectorstore path.
        collection_name: Optional collection name.
    """

    db_path: Path | None
    """Optional vectorstore path."""

    collection_name: str
    """Optional collection name."""

    def __init__(self, db_path: Path | str | None = None, collection_name: str = "memories") -> None:
        """
        Initialize the fake manager.

        Args:
            db_path (Path | str | None): Ignored vectorstore path.
            collection_name (str): Ignored collection name.
        """
        self.db_path = Path(db_path) if db_path is not None else None
        self.collection_name = collection_name

    def search(self, query: str, limit: int = 5, where_filter: dict | None = None) -> list[dict]:
        """
        Return deterministic memory matches.

        Args:
            query (str): Query text.
            limit (int): Maximum matches.
            where_filter (dict | None): Ignored metadata filter.

        Returns:
            list[dict]: Fake vectorstore results.
        """
        del query, where_filter
        return [
            {
                "id": "profiles.developer",
                "text": "Developer profile mentions unified query.",
                "category": "profiles",
                "key": "developer",
                "title": "Developer Profile",
                "similarity": 0.91,
                "metadata": {},
            },
            {
                "id": "memory.notes",
                "text": "Memory note should be filtered out.",
                "category": "memory.notes",
                "key": "notes",
                "title": "Memory Notes",
                "similarity": 0.89,
                "metadata": {},
            },
        ][:limit]


class FailingVectorStoreManager:
    """Test double that simulates embedding/vectorstore failure."""

    def search(self, query: str, limit: int = 5, where_filter: dict | None = None) -> list[dict]:
        """
        Raise a deterministic embedding failure.

        Args:
            query (str): Query text.
            limit (int): Maximum matches.
            where_filter (dict | None): Ignored metadata filter.

        Raises:
            RuntimeError: Always raised to simulate unavailable embeddings.
        """
        del query, limit, where_filter
        raise RuntimeError("Failed to fetch embedding: timeout")


class FakeKnowledgeVectorStoreManager:
    """Test double for knowledge vectorstore queries."""

    collection_name: str
    """Collection name requested by the caller."""

    def __init__(self, db_path: Path | str | None = None, collection_name: str = "memories") -> None:
        """Store constructor inputs for search branching."""
        del db_path
        self.collection_name = collection_name

    def search(self, query: str, limit: int = 5, where_filter: dict | None = None) -> list[dict]:
        """Return deterministic knowledge vector matches."""
        del query, where_filter
        if self.collection_name != "knowledge":
            return []
        return [
            {
                "id": "global:knowledge:relation:1",
                "text": "knowledge relation Legacy Vectorstore migrates_to Brain Vectorstore",
                "similarity": 0.94,
                "metadata": {
                    "knowledge_scope": "global",
                    "knowledge_kind": "relation",
                    "relation_id": 1,
                    "predicate": "migrates_to",
                    "subject_id": 10,
                    "subject_class": "MISC.RuntimeStore",
                    "subject_name": "Legacy Vectorstore",
                    "object_id": 11,
                    "object_class": "MISC.RuntimeStore",
                    "object_name": "Brain Vectorstore",
                    "source_path": "memory/query/default.md",
                },
            },
        ][:limit]


class GlobalQueryTests(unittest.TestCase):
    """Validate global query behavior across knowledge and memory."""

    def setUp(self) -> None:
        """Create an isolated knowledge runtime."""
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
        self.repository = KnowledgeRepository(knowledge_root=self.core_root / "database" / "knowledge")
        self.source_id = self.repository.upsert_source(
            source_dto=SourceDTO(
                source_type="memory",
                path="memory/query/default.md",
                title="query default",
            ),
        )

    def tearDown(self) -> None:
        """Restore environment variables and remove temporary files."""
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

    def test_query_global_returns_knowledge_matches(self) -> None:
        """Ensure `query` can search the knowledge graph directly."""
        self.repository.upsert_entity(
            EntityDTO(
                source_id=self.source_id,
                entity_class="concept",
                canonical_name="Unified Query Contract",
                description="A global query point searches anchored knowledge.",
                confidence=0.9,
            ),
        )

        results = query_global(text="anchored knowledge", scope="knowledge", limit=5)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].source, "knowledge")
        self.assertEqual(results[0].mechanism, "graph")
        self.assertEqual(results[0].title, "Unified Query Contract")
        self.assertEqual(results[0].source_ref.path, "memory/query/default.md")
        self.assertEqual(results[0].entities[0].entity_class, "MISC.Concept")
        self.assertEqual(results[0].entities[0].name, "Unified Query Contract")
        self.assertIn("anchored knowledge", results[0].content.excerpt)

    def test_query_global_supports_graph_mechanism(self) -> None:
        """Ensure `graph` selects the knowledge graph query backend."""
        self.repository.upsert_entity(
            EntityDTO(
                source_id=self.source_id,
                entity_class="concept",
                canonical_name="Graph Mechanism Contract",
                description="Graph mechanism searches the knowledge graph index.",
                confidence=0.9,
            ),
        )

        results = query_global(
            text="knowledge graph index",
            source="knowledge",
            mechanism="graph",
            limit=5,
        )

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].source, "knowledge")
        self.assertEqual(results[0].mechanism, "graph")
        self.assertEqual(results[0].title, "Graph Mechanism Contract")

    def test_query_global_returns_relation_context_from_graph(self) -> None:
        """Ensure KG search returns relation DTOs and endpoint entity context."""
        subject_id = self.repository.upsert_entity(
            EntityDTO(
                source_id=self.source_id,
                entity_class="MISC.RuntimeStore",
                canonical_name="Legacy Vectorstore",
                description="Old local vectorstore under the data directory.",
                confidence=0.91,
            ),
        )
        object_id = self.repository.upsert_entity(
            EntityDTO(
                source_id=self.source_id,
                entity_class="MISC.RuntimeStore",
                canonical_name="Brain Vectorstore",
                description="New local vectorstore under the database directory.",
                confidence=0.92,
            ),
        )
        self.repository.upsert_relation(
            RelationDTO(
                source_id=self.source_id,
                subject_id=subject_id,
                object_id=object_id,
                predicate="migrates_to",
                confidence=0.88,
            ),
        )

        results = query_global(
            text="legacy vectorstore migration database",
            source="knowledge",
            mechanism="graph",
            limit=5,
        )

        relation_results = [
            result
            for result in results
            if result.kind == "relation"
        ]
        self.assertGreaterEqual(len(relation_results), 1)
        relation_result = relation_results[0]
        self.assertEqual(relation_result.source_ref.path, "memory/query/default.md")
        self.assertEqual(relation_result.relations[0].predicate, "migrates_to")
        self.assertEqual(relation_result.relations[0].subject.name, "Legacy Vectorstore")
        self.assertEqual(relation_result.relations[0].object.name, "Brain Vectorstore")
        self.assertEqual(
            {entity.name for entity in relation_result.entities},
            {"Legacy Vectorstore", "Brain Vectorstore"},
        )

    def test_query_deep_segments_and_synthesizes_evidence(self) -> None:
        """Ensure deep mode plans subqueries and answers from KG evidence."""
        subject_id = self.repository.upsert_entity(
            EntityDTO(
                source_id=self.source_id,
                entity_class="MISC.RuntimeStore",
                canonical_name="Legacy Vectorstore",
                description="Old local vectorstore under the data directory.",
                confidence=0.91,
            ),
        )
        object_id = self.repository.upsert_entity(
            EntityDTO(
                source_id=self.source_id,
                entity_class="MISC.RuntimeStore",
                canonical_name="Brain Vectorstore",
                description="New local vectorstore under the database directory.",
                confidence=0.92,
            ),
        )
        self.repository.upsert_relation(
            RelationDTO(
                source_id=self.source_id,
                subject_id=subject_id,
                object_id=object_id,
                predicate="migrates_to",
                confidence=0.88,
            ),
        )

        with patch("brain.application.querying.entity_selection.request_query_json", side_effect=RuntimeError("no llm")):
            with patch("brain.application.querying.synthesis.request_query_json", side_effect=RuntimeError("no llm")):
                response = query_deep(
                    text="legacy vectorstore migration and database directory",
                    source="knowledge",
                    mechanism="graph",
                    knowledge_scope="global",
                    limit=5,
                )

        self.assertEqual(response.query, "legacy vectorstore migration and database directory")
        self.assertGreaterEqual(len(response.subqueries), 2)
        self.assertGreaterEqual(len(response.results), 1)
        self.assertIn("deep retrieval", response.answer)
        self.assertIn("Legacy Vectorstore", response.answer)
        self.assertIn("Brain Vectorstore", response.answer)
        self.assertNotIn("read:", response.answer)
        self.assertNotIn("memory/query/default.md", response.answer)
        self.assertTrue(any(result.relations for result in response.results))

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            print_human_deep_response(
                response_dto=response,
                color_enabled=False,
                explain=False,
            )
        rendered_output = stdout.getvalue()
        self.assertIn('readed `get-memory-entry "query.default"`', rendered_output)
        self.assertNotIn("memory/query/default.md", rendered_output)

    def test_query_context_parses_dates_by_language_modules(self) -> None:
        """Ensure deep context resolves supported English and Spanish dates."""
        as_of = datetime(2026, 7, 7, 15, 30, tzinfo=timezone.utc)

        spanish_context = build_query_context(text="que paso domingo y esta mañana", as_of=as_of)
        english_context = build_query_context(text="what happened yesterday and 2026-07-04", as_of=as_of)

        self.assertIn("2026-07-05", {constraint.label for constraint in spanish_context.date_constraints})
        self.assertTrue(any(constraint.granularity == "time_bucket" for constraint in spanish_context.date_constraints))
        self.assertIn("2026-07-06", {constraint.label for constraint in english_context.date_constraints})
        self.assertIn("2026-07-04", {constraint.label for constraint in english_context.date_constraints})

    def test_query_deep_filters_keyword_irrelevant_results(self) -> None:
        """Ensure deep ranking drops semantically close but lexically irrelevant evidence."""
        relevant = GlobalQueryResultDTO(
            source="knowledge",
            mechanism="graph",
            kind="entity",
            rank=0.2,
            title="Legacy Vectorstore",
            content=QueryContentDTO(excerpt="Legacy vectorstore migration touched the database directory."),
        )
        irrelevant = GlobalQueryResultDTO(
            source="knowledge",
            mechanism="graph",
            kind="entity",
            rank=0.01,
            title="Cooking Notes",
            content=QueryContentDTO(excerpt="Fresh bread and kitchen timing."),
        )

        with patch("brain.application.querying.service.query_global", return_value=[irrelevant, relevant]):
            with patch("brain.application.querying.synthesis.request_query_json", side_effect=RuntimeError("no llm")):
                response = query_deep(
                    text="legacy vectorstore migration",
                    source="knowledge",
                    mechanism="graph",
                    limit=5,
                )

        self.assertEqual([result.title for result in response.results], ["Legacy Vectorstore"])
        self.assertIn("keywords hit", response.results[0].match.explanation)

    def test_llm_entity_selector_success_and_invalid_fallback(self) -> None:
        """Ensure entity selection uses LLM output when valid and deterministic fallback when invalid."""
        context = build_query_context(text="legacy vectorstore migration", as_of=datetime(2026, 7, 7, tzinfo=timezone.utc))
        result = GlobalQueryResultDTO(
            source="knowledge",
            mechanism="graph",
            kind="entity",
            rank=0.1,
            title="Legacy Vectorstore",
            content=QueryContentDTO(excerpt="Legacy vectorstore migration."),
            entities=[
                {
                    "id": 7,
                    "entity_class": "MISC.RuntimeStore",
                    "name": "Legacy Vectorstore",
                    "description": "Old store.",
                    "confidence": 0.9,
                },
            ],
        )

        with patch("brain.application.querying.entity_selection.request_query_json", return_value={"entity_ids": [7]}):
            selected, warnings = select_deep_entities(context=context, results=[result])
        self.assertEqual(warnings, [])
        self.assertEqual(selected[0].selector_source, "llm")

        with patch("brain.application.querying.entity_selection.request_query_json", side_effect=RuntimeError("bad json")):
            selected, warnings = select_deep_entities(context=context, results=[result])
        self.assertEqual(selected[0].selector_source, "deterministic")
        self.assertTrue(any("deterministic selector used" in warning for warning in warnings))

    def test_query_global_supports_knowledge_vector_mechanism(self) -> None:
        """Ensure knowledge vector search returns normalized KG vector evidence."""
        (self.core_root / "database" / "vectorstores" / "brain_vectorstore").mkdir(parents=True)
        with patch("brain.application.knowledge.vector_sync.VectorStoreManager", FakeKnowledgeVectorStoreManager):
            results = query_global(
                text="legacy vectorstore migration",
                source="knowledge",
                mechanism="vector",
                knowledge_scope="global",
                limit=5,
            )

        self.assertEqual(results[0].source, "knowledge")
        self.assertEqual(results[0].mechanism, "vector")
        self.assertEqual(results[0].kind, "relation_vector")
        self.assertEqual(results[0].relations[0].predicate, "migrates_to")

    def test_source_references_expose_reader_commands(self) -> None:
        """Ensure source references expose commands instead of physical paths."""
        diary_ref = source_ref_from_path(path="memory/diary/2026-06/28-06-2026.md")
        diary_entry_ref = source_ref_from_path(path="memory/diary/2026-06/28-06-2026.md", entry_time="17:46")
        memory_ref = source_ref_from_path(path="memory/profiles/developer.md")
        profile_entry_ref = source_ref_from_path(path="memory/profiles/developer/1 - instructions.md")
        log_ref = source_ref_from_path(path="$agent/logs/2026-07/04-07-2026.log.md")

        self.assertEqual(diary_ref.domain, "diary.2026-06.28-06-2026")
        self.assertEqual(diary_ref.read_command, "read-diary -d 28-06-2026")
        self.assertEqual(diary_entry_ref.read_command, "read-diary -d 28-06-2026 --time 17:46")
        self.assertEqual(memory_ref.domain, "profiles.developer")
        self.assertEqual(memory_ref.read_command, "read-profile developer")
        self.assertEqual(profile_entry_ref.read_command, "read-profile developer")
        self.assertEqual(log_ref.domain, "$agent.logs.2026-07.04-07-2026")
        self.assertEqual(log_ref.read_command, "read-log -d 04-07-2026")

    def test_direct_text_results_expose_exact_diary_entry_commands(self) -> None:
        """Ensure text matches inside diary entries expose exact minute readers."""
        memory_root = self.root / "memory"
        diary_path = memory_root / "diary" / "2026-06" / "28-06-2026.md"
        diary_path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(
            [
                "# Diary",
                "",
                "## 28-06-2026 17:46:00 - Exact entry",
                "Body with searchable Mimi detail.",
                "",
                "## 28-06-2026 18:00:00 - Other entry",
                "Other body.",
            ],
        )
        diary_path.write_text(content, encoding="utf-8")

        result = build_memory_text_result(
            markdown_path=diary_path,
            memory_root=memory_root,
            content=content,
            line="Body with searchable Mimi detail.",
            line_number=4,
            matches=[("Mimi", 21, 25)],
            rank=0.1,
        )

        self.assertEqual(result.source_ref.read_command, "read-diary -d 28-06-2026 --time 17:46")
        self.assertEqual(result.source_ref.title, "Exact entry")
        self.assertNotIn("## 28-06-2026", result.content.excerpt)

    def test_query_global_searches_source_scoped_type_assertions(self) -> None:
        """Ensure KG search uses contextual type assertions, not only entity names."""
        entity_id = self.repository.upsert_entity(
            EntityDTO(
                source_id=self.source_id,
                entity_class="FILE.MarkdownDoc",
                canonical_name="README.md",
                description="Repository entrypoint document.",
                confidence=0.91,
            ),
        )

        results = query_global(
            text="MarkdownDoc repository entrypoint",
            source="knowledge",
            mechanism="graph",
            limit=5,
        )

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].entities[0].id, entity_id)
        self.assertIn(
            "FILE.MarkdownDoc",
            {
                assertion["entity_class"]
                for assertion in results[0].entities[0].type_assertions
            },
        )

    def test_query_global_rejects_legacy_fts_mechanism(self) -> None:
        """Ensure the public query mechanism is `graph`, not the internal SQLite FTS detail."""
        with self.assertRaises(ValueError):
            query_global(
                text="knowledge graph",
                source="knowledge",
                mechanism="fts",
                limit=5,
            )

    def test_query_global_filters_memory_domain(self) -> None:
        """Ensure legacy `query domain text` filtering still works for memory."""
        with patch("brain.infrastructure.vectorstores.manager.VectorStoreManager", FakeVectorStoreManager):
            results = query_global(
                text="unified query",
                domain="profiles",
                scope="memory",
                mechanism="vector",
                limit=5,
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "memory")
        self.assertEqual(results[0].title, "Developer Profile")
        self.assertEqual(results[0].mechanism, "vector")
        self.assertEqual(results[0].source_ref.path, "memory/profiles/developer.md")
        self.assertIn("Developer profile", results[0].content.excerpt)

    def test_query_global_supports_direct_text_mechanism(self) -> None:
        """Ensure removed `search` behavior is available through `query --mechanism text`."""
        notes_dir = self.root / "memory" / "notes"
        notes_dir.mkdir(parents=True)
        note_path = notes_dir / "unified.md"
        note_path.write_text(
            "# Unified Search\n\nThe global query command performs direct text search.",
            encoding="utf-8",
        )

        results = query_global(
            text="direct text search",
            source="memory",
            mechanism="text",
            limit=5,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "memory")
        self.assertEqual(results[0].mechanism, "text")
        self.assertEqual(results[0].kind, "text_memory")
        self.assertEqual(results[0].title, "notes/unified")
        self.assertEqual(results[0].source_ref.path, "memory/notes/unified.md")
        self.assertIn("global query command", results[0].content.excerpt)

    def test_query_global_text_matching_uses_language_modules(self) -> None:
        """Ensure direct text search uses language module normalization."""
        notes_dir = self.root / "memory" / "notes"
        notes_dir.mkdir(parents=True)
        note_path = notes_dir / "spanish.md"
        note_path.write_text(
            "# Nota\n\nEl detalle de mañana queda registrado.",
            encoding="utf-8",
        )

        results = query_global(
            text="manana queda",
            source="memory",
            mechanism="text",
            limit=5,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "notes/spanish")
        self.assertIn("mañana queda registrado", results[0].content.excerpt)

    def test_query_global_keeps_knowledge_when_memory_fails(self) -> None:
        """Ensure vectorstore failures do not block KG results."""
        self.repository.upsert_entity(
            EntityDTO(
                source_id=self.source_id,
                entity_class="concept",
                canonical_name="Fallback Knowledge Result",
                description="Knowledge remains searchable when embeddings fail.",
                confidence=0.9,
            ),
        )

        with patch("brain.infrastructure.vectorstores.manager.VectorStoreManager", FailingVectorStoreManager):
            results = query_global(text="embeddings fail", scope="all", limit=5)

        result_sources = {result.source for result in results}
        result_kinds = {result.kind for result in results}
        self.assertIn("knowledge", result_sources)
        self.assertIn("memory", result_sources)
        self.assertIn("warning", result_kinds)

    def test_cli_registers_query_as_global_and_removes_search(self) -> None:
        """Ensure `query` is the only global consultation entry point."""
        from brain.presentation.commands.registry import COMMAND_MODULES

        command_schemas = {
            command_module.SCHEMA.name: command_module.SCHEMA
            for command_module in COMMAND_MODULES
        }

        self.assertIn("query", command_schemas)
        self.assertIn("knowledge-deltas", command_schemas)
        self.assertIn("delete-knowledge-deltas", command_schemas)
        self.assertNotIn("search", command_schemas)
        self.assertNotIn("knowledge-ingest", command_schemas)
        self.assertEqual(command_schemas["query"].domain, "general")
        dream_flags = {
            flag
            for argument in command_schemas["dream"].arguments
            for flag in argument.flags
        }
        knowledge_delta_flags = {
            flag
            for argument in command_schemas["knowledge-deltas"].arguments
            for flag in argument.flags
        }
        self.assertIn("--prune", dream_flags)
        self.assertNotIn("--apply", dream_flags)
        self.assertNotIn("--apply", knowledge_delta_flags)
        self.assertNotIn("--dry-run", dream_flags)
        query_flags = {
            flag
            for argument in command_schemas["query"].arguments
            for flag in argument.flags
        }
        self.assertIn("--deep", query_flags)
        self.assertNotIn("--response", query_flags)

    def test_help_supports_command_domains(self) -> None:
        """Ensure focused help accepts domain topics such as `knowledge`."""
        help_text = get_command_help_text(topic="knowledge", color=False)

        self.assertIn("Domain:", help_text)
        self.assertIn("knowledge - Command group.", help_text)
        self.assertIn("knowledge-deltas", help_text)
        self.assertIn("dream", help_text)
        self.assertNotIn("--apply", help_text)
        self.assertIn("  --id <ID> - Review one pending delta by identifier.", help_text)
        self.assertNotIn("knowledge-deltas: --id", help_text)
        self.assertNotIn("  knowledge-deltas\n    --id", help_text)

    def test_short_help_lists_only_domains_and_commands(self) -> None:
        """Ensure short help omits syntax, parameters, and descriptions."""
        help_text = get_short_help_text(color=False)
        knowledge_text = get_short_help_text(topic="knowledge", color=False)

        self.assertIn("Domains:", help_text)
        self.assertIn("  knowledge:", help_text)
        self.assertIn("    - knowledge-deltas", help_text)
        self.assertIn("    - dream", knowledge_text)
        self.assertIn("    - knowledge-status", knowledge_text)
        self.assertNotIn("Parameters:", help_text)
        self.assertNotIn("--scope", help_text)
        self.assertNotIn("Command:", help_text)
        self.assertNotIn("Command group.", help_text)


if __name__ == "__main__":
    unittest.main()
