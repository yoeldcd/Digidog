"""Regression tests for records, policy aliases, and memory-entry boundaries."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from brain.application.records import service as record_service
from brain.application.records.service import add_live_record, delete_live_record, list_live_records
from brain.presentation.actions.records import command_add_record as add_record_action
from brain.presentation.actions.records import command_delete_record as delete_record_action
from brain.presentation.actions.records import command_show_records as show_records_action
from brain.presentation.actions.registry import ACTION_HANDLERS
from brain.presentation.commands.memory import command_delete_memory_entry, command_get_memory_entry, command_set_memory_entry
from brain.presentation.commands.records import command_add_record, command_delete_record, command_show_records


class RecordCommandBoundaryTest(unittest.TestCase):
    """Keep one records layer independent from Markdown memory entries."""

    def test_memory_and_record_schemas_have_distinct_domains(self) -> None:
        self.assertEqual(command_get_memory_entry.SCHEMA.domain, "memory")
        self.assertEqual(command_set_memory_entry.SCHEMA.domain, "memory")
        self.assertEqual(command_delete_memory_entry.SCHEMA.domain, "memory")
        self.assertEqual(command_add_record.SCHEMA.domain, "records")
        self.assertEqual(command_show_records.SCHEMA.domain, "records")
        self.assertEqual(command_delete_record.SCHEMA.domain, "records")

    def test_policy_spellings_are_aliases_not_separate_commands(self) -> None:
        self.assertEqual(command_add_record.SCHEMA.aliases, ["registre-policie"])
        self.assertEqual(command_show_records.SCHEMA.aliases, ["show-policies"])
        self.assertEqual(command_delete_record.SCHEMA.aliases, ["deprecate-policie"])
        self.assertNotIn("registre-policie", ACTION_HANDLERS)
        self.assertNotIn("show-policies", ACTION_HANDLERS)
        self.assertNotIn("deprecate-policie", ACTION_HANDLERS)
        for name in ("add-record", "show-records", "delete-record"):
            self.assertTrue(ACTION_HANDLERS[name].startswith("brain.presentation.actions.records."), name)

    def test_records_source_contracts_are_documented(self) -> None:
        """Require documentation on every records module and callable boundary."""
        modules = (
            record_service,
            command_add_record,
            command_show_records,
            command_delete_record,
            add_record_action,
            show_records_action,
            delete_record_action,
        )
        for module in modules:
            with self.subTest(module=module.__name__):
                self.assertTrue(module.__doc__ and module.__doc__.strip())
        for function in (
            record_service.records_path,
            record_service.list_live_records,
            record_service.read_live_record,
            record_service.add_live_record,
            record_service.delete_live_record,
            add_record_action.handle,
            show_records_action.handle,
            delete_record_action.handle,
        ):
            with self.subTest(function=function.__qualname__):
                self.assertTrue(function.__doc__ and function.__doc__.strip())
    def test_record_store_preserves_public_json_contract(self) -> None:
        temp_root = Path("$agent/.tmp")
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as directory:
            root = Path(directory)
            created = add_live_record("Always validate the result.", workspace_root=root)
            self.assertEqual(created.id, "rec01")
            self.assertEqual([record.text for record in list_live_records(workspace_root=root)], ["Always validate the result."])
            payload = json.loads((root / "$agent" / "data" / "records.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["records"][0]["id"], "rec01")
            self.assertEqual(delete_live_record("rec01", workspace_root=root).id, "rec01")
            self.assertEqual(list_live_records(workspace_root=root), [])


if __name__ == "__main__":
    unittest.main()
