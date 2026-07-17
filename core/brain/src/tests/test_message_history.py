# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Tests for workspace-local avatar message history."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from brain.infrastructure.messages.models import MessageWriteDTO
from brain.infrastructure.messages.repository import MessageRepository, should_persist_message
from brain.application.knowledge.sources.discovery import discover_sources
from brain.application.knowledge.sources.file_reader import read_source_text


class MessageRepositoryTests(unittest.TestCase):
    """Validate schema, idempotency, filters, and Dream projection."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name)
        self.repository = MessageRepository(
            consumer_path=self.workspace,
            require_registered=False,
        )
        self.repository.initialize()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_append_is_idempotent_and_projects_date_time(self) -> None:
        """One speak identifier must produce exactly one persisted record."""
        message = MessageWriteDTO(
            id="speak-001",
            created_at="2026-07-16T23:45:10+03:00",
            text="Hola, papi.",
            emotion="happy",
            chat_id="chat-1",
        )
        self.assertTrue(self.repository.append(message=message))
        self.assertFalse(self.repository.append(message=message))
        mapping = self.repository.list_messages(limit=10)[0].as_mapping()
        self.assertEqual(mapping["date"], "2026-07-16")
        self.assertEqual(mapping["time"], "23:45:10+03:00")
        self.assertEqual(self.repository.count(), 1)
        self.assertEqual(self.repository.get_message("speak-001").text, "Hola, papi.")
        self.assertIsNone(self.repository.get_message("missing"))

    def test_filters_and_markdown_projection(self) -> None:
        """Explorer filters and Dream export must retain operation metadata."""
        self.repository.append(
            message=MessageWriteDTO(
                id="speak-002",
                created_at="2026-07-16T23:46:10+03:00",
                text="He completado el trabajo.",
                emotion="proud",
                chat_id="chat-2",
                source_type="operation",
                source_command="complete-work",
                source_phase="output",
            ),
        )
        records = self.repository.list_messages(
            query="completado",
            emotion="proud",
            source_command="complete-work",
        )
        self.assertEqual(len(records), 1)
        markdown = self.repository.export_markdown()
        self.assertIn("complete-work:output", markdown)
        self.assertIn("He completado el trabajo.", markdown)

    def test_session_summaries_group_by_day_and_chat(self) -> None:
        """Explorer navigation must expose stable daily session leaves."""
        for identifier, created_at, chat_id in (
            ("speak-a", "2026-07-16T23:46:10+03:00", "chat-one"),
            ("speak-b", "2026-07-16T23:47:10+03:00", "chat-one"),
            ("speak-c", "2026-07-17T08:00:00+03:00", ""),
        ):
            self.repository.append(
                message=MessageWriteDTO(
                    id=identifier,
                    created_at=created_at,
                    text=f"Message {identifier}",
                    chat_id=chat_id,
                ),
            )

        sessions = self.repository.list_session_summaries()

        self.assertEqual([session["id"] for session in sessions], [
            "2026-07-17::unassigned",
            "2026-07-16::chat-one",
        ])
        self.assertEqual(sessions[1]["messageCount"], 2)
        unassigned = self.repository.list_messages(
            date="2026-07-17",
            chat_id_exact="",
        )
        self.assertEqual([record.id for record in unassigned], ["speak-c"])

    def test_only_selected_operations_are_persistable(self) -> None:
        """Manual speaks and approved operation narrations pass the policy."""
        self.assertTrue(should_persist_message(""))
        self.assertTrue(should_persist_message("complete-work"))
        self.assertTrue(should_persist_message("append-log"))
        self.assertTrue(should_persist_message("add-log"))
        self.assertTrue(should_persist_message("add-task"))
        self.assertFalse(should_persist_message("query"))

    def test_local_dream_discovers_and_reads_message_database(self) -> None:
        """The message database must be a virtual local Dream source."""
        self.repository.append(
            message=MessageWriteDTO(
                id="speak-003",
                created_at="2026-07-16T23:47:10+03:00",
                text="Conocimiento recuperable.",
            ),
        )
        candidates = discover_sources(
            domain="messages",
            workspace_root=self.workspace,
            source_scope="local",
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].source_dto.path, "$agent/database/messages.db")
        self.assertIn("Conocimiento recuperable.", read_source_text(path=candidates[0].path))


if __name__ == "__main__":
    unittest.main()
