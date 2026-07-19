"""Focused regression tests for reference-only vector records."""

from __future__ import annotations

import argparse
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from brain.application.logs.records import LogEntryRecord
from brain.application.logs.store import insert_log_entry, list_log_entries
from brain.application.knowledge.vector_sync import entity_vector_metadata, hydrate_knowledge_vector_match
import brain.infrastructure.vectorstores.generations as generations_module
from brain.infrastructure.vectorstores.generations import replace_vectorstore_generation, validate_vectorstore_generation
from brain.infrastructure.vectorstores.logs import index_log_entries, search_logs
from brain.infrastructure.vectorstores.manager import VectorStoreManager
from brain.infrastructure.vectorstores.messages import sync_all_message_vectors
from brain.infrastructure.vectorstores.pictures import sync_picture_vectors
from brain.presentation.actions.vectorstore import command_rebuild_vectorstore, command_update_vectorstore


class CapturingCollection:
    """Capture Chroma add calls without opening a persistent database."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def add(self, **kwargs: object) -> None:
        """Record one collection add operation."""
        self.calls.append(dict(kwargs))


class CapturingManager:
    """Capture vector records through the log and message protocols."""

    instances: list["CapturingManager"] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self.records: list[tuple[str, str, dict]] = []
        self.collection = SimpleNamespace(get=lambda **_kwargs: {"metadatas": []})
        self.__class__.instances.append(self)

    def count_records(self) -> int:
        return 0

    def reset_store(self) -> None:
        return None

    def delete_by_metadata(self, filter_dict: dict) -> int:
        del filter_dict
        return 0

    def add_record(self, doc_id: str, text: str, metadata: dict, embedding: list[float] | None = None) -> None:
        del embedding
        self.records.append((doc_id, text, metadata))

    def close(self) -> None:
        return None


class VectorReferenceContractTests(unittest.TestCase):
    """Verify vectors persist identifiers while canonical stores retain text."""

    def test_manager_omits_chroma_documents(self) -> None:
        """Ensure transient text is embedded but never passed as a Chroma document."""
        manager = VectorStoreManager.__new__(VectorStoreManager)
        manager.collection = CapturingCollection()
        manager.delete_record = lambda _doc_id: None
        manager.add_record(doc_id="record:1", text="canonical text", metadata={"record_id": 1}, embedding=[0.5])
        call = manager.collection.calls[0]
        self.assertNotIn("documents", call)
        self.assertEqual(call["metadatas"], [{"record_id": 1, "vector_reference": "record:1"}])

    def test_knowledge_reference_hydrates_query_fields_without_changing_storage_contract(self) -> None:
        """Ensure SQLite hydration restores presentation fields while stored metadata remains minimal."""
        entity_row = {
            "id": 7,
            "entity_class": "MODULE",
            "canonical_name": "Vector Stores",
            "description": "Similarity index storage.",
            "source_path": "",
            "source_type": "",
            "source_title": "",
            "type_assertions": [
                {
                    "source_path": "memory/architecture.md",
                    "source_type": "memory",
                    "source_title": "Architecture",
                },
            ],
        }
        stored_metadata = entity_vector_metadata(scope="global", entity_row=entity_row)
        repository = SimpleNamespace(scope="global", get_entity=lambda record_id: entity_row if record_id == 7 else None)
        match = {"text": "", "metadata": stored_metadata}
        hydrated = hydrate_knowledge_vector_match(repository=repository, match=match)
        self.assertEqual(stored_metadata, {"knowledge_scope": "global", "knowledge_kind": "entity", "record_id": 7})
        self.assertEqual(hydrated["metadata"]["entity_name"], "Vector Stores")
        self.assertEqual(hydrated["metadata"]["source_path"], "memory/architecture.md")

    def test_log_vectors_store_only_sqlite_reference_and_hydrate(self) -> None:
        """Ensure log result fields are recovered from the canonical SQLite row."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            insert_log_entry(
                workspace_root=root,
                entry=LogEntryRecord(
                    timestamp="17-07-2026 10:15 pm",
                    domain="core.vectorstore",
                    title="Reference-only logs",
                    change_type="fix",
                    why="Avoid duplication.",
                    description="Hydrate the canonical row.",
                    impact="Smaller vectors.",
                ),
            )
            entry = list_log_entries(workspace_root=root)[0]
            manager = CapturingManager()
            index_log_entries(manager=manager, entries=[entry])
            doc_id, _text, metadata = manager.records[0]
            self.assertEqual(doc_id, f"log.db#{entry.record_id}")
            self.assertEqual(metadata, {"source_kind": "log", "source_backend": "sqlite", "record_id": entry.record_id})
            manager.search = lambda *_args, **_kwargs: [{"id": doc_id, "text": "", "similarity": 0.9, "metadata": metadata}]
            with patch("brain.infrastructure.runtime.paths.get_workspace_root", return_value=root):
                match = search_logs(manager=manager, query="canonical", limit=1)[0]
            self.assertEqual(match["title"], "Reference-only logs")
            self.assertIn("Hydrate the canonical row.", match["text"])

    def test_message_sync_persists_consumer_and_message_references_only(self) -> None:
        """Ensure message content is transient input rather than vector metadata."""
        consumer = Path("D:/consumer").resolve()
        record = SimpleNamespace(id="message-1", text="A canonical message")
        repository = SimpleNamespace(list_messages=lambda limit, offset: [record] if offset == 0 else [])
        CapturingManager.instances.clear()
        with patch("brain.infrastructure.vectorstores.messages.VectorStoreManager", CapturingManager), patch(
            "brain.infrastructure.vectorstores.messages.registered_consumer_paths", return_value=[consumer]
        ), patch("brain.infrastructure.vectorstores.messages.message_database_path", return_value=Path(__file__)), patch(
            "brain.infrastructure.vectorstores.messages.MessageRepository", return_value=repository
        ):
            stats = sync_all_message_vectors(db_path=Path("D:/vectors"))
        _doc_id, text, metadata = CapturingManager.instances[0].records[0]
        self.assertEqual(text, record.text)
        self.assertEqual(metadata, {"source_kind": "message", "consumer_path": consumer.as_posix(), "message_id": record.id})
        self.assertTrue(stats["reference_only"])

    def test_picture_sync_persists_only_canonical_picture_reference(self) -> None:
        """Ensure picture vectors contain no path, description, or image bytes."""
        record = SimpleNamespace(
            id="picture-1", filename="family-dinner.png", domain="family",
            relative_path="family/dinner.png", description="A shared dinner.",
            vector_fingerprint="",
        )
        repository = SimpleNamespace(
            list=lambda: [record],
            mark_vector_indexed=lambda picture_id, fingerprint: None,
        )
        CapturingManager.instances.clear()
        with patch("brain.infrastructure.vectorstores.pictures.scan_pictures", return_value={"unchanged": 1}), patch(
            "brain.infrastructure.vectorstores.pictures.PictureRepository", return_value=repository
        ), patch("brain.infrastructure.vectorstores.pictures.VectorStoreManager", CapturingManager), patch(
            "brain.infrastructure.vectorstores.pictures.project_picture_descriptions",
            return_value={"pictures": 1, "characters": 0, "tags": 0},
        ), patch("brain.infrastructure.vectorstores.pictures.load_pictures_config"):
            stats = sync_picture_vectors(db_path=Path("D:/vectors"))
        _doc_id, text, metadata = CapturingManager.instances[0].records[0]
        self.assertIn("A shared dinner.", text)
        self.assertEqual(metadata, {"source_kind": "picture", "picture_id": record.id})
        self.assertTrue(stats["reference_only"])

    def test_global_update_and_rebuild_include_message_sync(self) -> None:
        """Ensure both global maintenance actions connect the message collection."""
        class ActionManager:
            def __init__(self) -> None:
                self.collection = SimpleNamespace(get=lambda **_kwargs: {"ids": [], "metadatas": []})

            def count_records(self) -> int:
                return 0

            def reset_store(self) -> None:
                return None

        args = argparse.Namespace(json=True, color=False, verbose_log=False, best_effort=False, yes=True)
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(command_update_vectorstore, "MEMORY_ROOT", temp_dir), patch.object(
            command_update_vectorstore, "VectorStoreManager", ActionManager
        ), patch.object(command_update_vectorstore, "sync_all_knowledge_vectorstores", return_value=([], [])), patch.object(
            command_update_vectorstore, "sync_all_message_vectors", return_value={"entries_created": 1}
        ) as update_sync, patch.object(
            command_update_vectorstore, "sync_picture_vectors", return_value={"entries_created": 1}
        ), redirect_stdout(io.StringIO()):
            self.assertEqual(command_update_vectorstore.handle(args), 0)
            update_sync.assert_called_once_with()
        generation_result = {
            "build": {"indexed_files": 1, "total_discovered": 1, "entries_created": 1},
            "validation": {"collections": {"memories": 1, "knowledge": 0, "messages": 0}},
        }
        with patch.object(
            command_rebuild_vectorstore,
            "replace_vectorstore_generation",
            return_value=generation_result,
        ) as replace_generation, redirect_stdout(io.StringIO()):
            self.assertEqual(command_rebuild_vectorstore.handle(args), 0)
            replace_generation.assert_called_once()

    def test_generation_swap_retires_old_directory_without_residue(self) -> None:
        """Ensure a validated generation replaces and removes the prior directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            active = Path(temp_dir) / "vectorstores"
            active.mkdir()
            (active / "old.txt").write_text("old", encoding="utf-8")

            def build(path: Path) -> dict[str, object]:
                path.mkdir()
                (path / "new.txt").write_text("new", encoding="utf-8")
                return {"built": True}

            result = replace_vectorstore_generation(active, build, lambda _path: {"valid": True})
            self.assertTrue((active / "new.txt").is_file())
            self.assertFalse((active / "old.txt").exists())
            self.assertEqual(list(Path(temp_dir).glob(".vectorstores.*")), [])
            self.assertTrue(result["replaced_existing"])

    def test_generation_build_failure_preserves_active_directory(self) -> None:
        """Ensure a failed isolated build cannot disturb the active generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            active = Path(temp_dir) / "vectorstores"
            active.mkdir()
            (active / "old.txt").write_text("old", encoding="utf-8")

            def fail_build(path: Path) -> dict[str, object]:
                path.mkdir()
                raise RuntimeError("build failed")

            with self.assertRaisesRegex(RuntimeError, "build failed"):
                replace_vectorstore_generation(active, fail_build, lambda _path: {})
            self.assertEqual((active / "old.txt").read_text(encoding="utf-8"), "old")
            self.assertEqual(list(Path(temp_dir).glob(".vectorstores.*")), [])

    def test_generation_install_failure_rolls_back_prior_directory(self) -> None:
        """Ensure a failed second rename restores the retired generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            active = Path(temp_dir) / "vectorstores"
            active.mkdir()
            (active / "old.txt").write_text("old", encoding="utf-8")
            real_replace = os.replace
            call_count = 0

            def replace_with_install_failure(source: Path, target: Path) -> None:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise OSError("install failed")
                real_replace(source, target)

            def build(path: Path) -> dict[str, object]:
                path.mkdir()
                (path / "new.txt").write_text("new", encoding="utf-8")
                return {}

            with patch.object(generations_module.os, "replace", side_effect=replace_with_install_failure):
                with self.assertRaisesRegex(OSError, "install failed"):
                    replace_vectorstore_generation(active, build, lambda _path: {})
            self.assertEqual((active / "old.txt").read_text(encoding="utf-8"), "old")
            self.assertEqual(list(Path(temp_dir).glob(".vectorstores.*")), [])

    def test_generation_validation_rejects_legacy_collections_and_releases_client(self) -> None:
        """Ensure validation checks the exact collection set without retaining file locks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            generation = Path(temp_dir) / "vectorstores"
            memory_manager = VectorStoreManager(db_path=generation, collection_name="memories")
            memory_manager.add_record("memory:1", "text", {"record_id": 1}, embedding=[0.1, 0.2, 0.3])
            memory_manager.close()
            for collection_name in ("knowledge", "messages", "pictures"):
                manager = VectorStoreManager(db_path=generation, collection_name=collection_name)
                manager.close()
            result = validate_vectorstore_generation(generation, {"memories", "knowledge", "messages", "pictures"})
            self.assertEqual(result["total_vectors"], 1)
            legacy_manager = VectorStoreManager(db_path=generation, collection_name="legacy")
            legacy_manager.close()
            with self.assertRaisesRegex(RuntimeError, "collections mismatch"):
                validate_vectorstore_generation(generation, {"memories", "knowledge", "messages", "pictures"})

    def test_retired_cleanup_failure_restores_prior_generation(self) -> None:
        """Ensure cleanup failure rolls back instead of leaving the new generation active."""
        with tempfile.TemporaryDirectory() as temp_dir:
            active = Path(temp_dir) / "vectorstores"
            active.mkdir()
            (active / "old.txt").write_text("old", encoding="utf-8")
            real_remove = generations_module._remove_generation

            def fail_retired_cleanup(path: Path, parent: Path) -> None:
                if ".retired-" in path.name:
                    raise OSError("cleanup failed")
                real_remove(path=path, parent=parent)

            def build(path: Path) -> dict[str, object]:
                path.mkdir()
                (path / "new.txt").write_text("new", encoding="utf-8")
                return {}

            with patch.object(generations_module, "_remove_generation", side_effect=fail_retired_cleanup):
                with self.assertRaisesRegex(OSError, "cleanup failed"):
                    replace_vectorstore_generation(active, build, lambda _path: {})
            self.assertEqual((active / "old.txt").read_text(encoding="utf-8"), "old")
            self.assertEqual(list(Path(temp_dir).glob(".vectorstores.*")), [])

    def test_isolated_builder_targets_every_collection_to_generation_path(self) -> None:
        """Ensure memory, knowledge, and messages are built only under the supplied generation."""
        class BuildManager:
            def __init__(self, db_path: Path, collection_name: str) -> None:
                self.db_path = db_path
                self.collection_name = collection_name

            def close(self) -> None:
                return None

        args = argparse.Namespace(json=True, verbose_log=False)
        with tempfile.TemporaryDirectory() as temp_dir:
            generation = Path(temp_dir) / "generation"
            memory_root = Path(temp_dir) / "memory"
            memory_root.mkdir()
            with patch.object(command_rebuild_vectorstore, "MEMORY_ROOT", memory_root), patch.object(
                command_rebuild_vectorstore, "VectorStoreManager", BuildManager
            ), patch.object(
                command_rebuild_vectorstore,
                "sync_all_knowledge_vectorstores",
                return_value=([], []),
            ) as knowledge_sync, patch.object(
                command_rebuild_vectorstore,
                "sync_all_message_vectors",
                return_value={"entries_created": 0},
            ) as message_sync:
                with patch.object(
                    command_rebuild_vectorstore,
                    "sync_picture_vectors",
                    return_value={"entries_created": 0},
                ) as picture_sync:
                    command_rebuild_vectorstore.build_vectorstore_generation(generation, args, False)
            knowledge_sync.assert_called_once_with(vectorstore_path=generation)
            message_sync.assert_called_once_with(db_path=generation, reset=False)
            picture_sync.assert_called_once_with(db_path=generation, reset=False)


if __name__ == "__main__":
    unittest.main()
