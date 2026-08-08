"""Focused security and transactional tests for the guarded patch engine."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from brain.application.patching.specification import PatchSpecificationError, parse_patch_request
from brain.infrastructure.patching.filesystem_patch_engine import FileSystemPatchEngine, PatchExecutionError
from brain.infrastructure.runtime.paths import get_transient_dir


class FileSystemPatchEngineTest(unittest.TestCase):
    """Verify strict schema, confinement, encodings, and batch recovery."""

    def test_omitted_new_is_rejected_before_filesystem_access(self) -> None:
        """Reject null or absent replacement text during schema parsing."""
        specification = json.dumps({"edits": [{"path": "missing.txt", "replacements": [{"old": "old", "expectedOccurrences": 1}]}]})

        with self.assertRaisesRegex(PatchSpecificationError, "new must be a string"):
            parse_patch_request(specification)

    def test_empty_results_require_explicit_boolean_opt_in(self) -> None:
        """Reject empty creates and edits unless allowEmptyResult is strictly true."""
        with self.assertRaisesRegex(PatchSpecificationError, "content is empty"):
            parse_patch_request(json.dumps({"creates": [{"path": "new.txt", "content": ""}]}))
        with self.assertRaisesRegex(PatchSpecificationError, "allowEmptyResult must be a boolean"):
            parse_patch_request(json.dumps({"creates": [{"path": "new.txt", "content": "", "allowEmptyResult": 1}]}))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.txt"
            target.write_text("remove", encoding="utf-8")
            request = parse_patch_request(json.dumps({"edits": [{"path": "target.txt", "allowEmptyResult": True, "replacements": [{"old": "remove", "new": "", "expectedOccurrences": 1}]}]}))
            FileSystemPatchEngine(root).execute(request, check=False)
            self.assertEqual(target.read_bytes(), b"")

    def test_check_plans_without_writing_and_evidence_is_redacted(self) -> None:
        """Keep check mode write-free while exposing hashes, lengths, and counts only."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.txt"
            target.write_text("secret old source", encoding="utf-8")
            request = parse_patch_request(json.dumps({"edits": [{"path": "target.txt", "replacements": [{"old": "old", "new": "new secret", "expectedOccurrences": 1}]}]}))

            result = FileSystemPatchEngine(root).execute(request, check=True)

            self.assertEqual(target.read_text(encoding="utf-8"), "secret old source")
            evidence = result.files[0]
            self.assertEqual(evidence.replacement_count, 1)
            self.assertEqual(len(evidence.after_sha256), 64)
            self.assertNotIn("secret", repr(evidence))
            self.assertFalse(list(root.glob(".brain-patch-*")))

    def test_traversal_and_reparse_point_are_rejected(self) -> None:
        """Reject lexical traversal and a physical symlink target path."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspace"
            root.mkdir()
            outside = root.parent / "outside.txt"
            outside.write_text("old", encoding="utf-8")
            traversal = parse_patch_request(json.dumps({"edits": [{"path": "../outside.txt", "replacements": [{"old": "old", "new": "new", "expectedOccurrences": 1}]}]}))
            with self.assertRaisesRegex(PatchExecutionError, "traversal"):
                FileSystemPatchEngine(root).execute(traversal, check=True)

            linked = root / "linked"
            linked.mkdir()
            reparse = parse_patch_request(json.dumps({"creates": [{"path": "linked/new.txt", "content": "safe"}]}))
            engine = FileSystemPatchEngine(root)
            original_is_reparse = engine._is_reparse

            def mark_linked_as_reparse(path: Path) -> bool:
                """Simulate a filesystem junction where symlinks need privileges."""
                return path == linked or original_is_reparse(path)

            engine._is_reparse = mark_linked_as_reparse
            with self.assertRaisesRegex(PatchExecutionError, "reparse point"):
                engine.execute(reparse, check=True)

    def test_supported_bom_and_encoding_are_preserved(self) -> None:
        """Preserve UTF-8 BOM and UTF-16 little-endian BOM after exact edits."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            utf8_target = root / "utf8.txt"
            utf8_target.write_bytes(b"\xef\xbb\xbfalpha")
            utf16_target = root / "utf16.txt"
            utf16_target.write_bytes(b"\xff\xfe" + "alpha".encode("utf-16-le"))
            request = parse_patch_request(json.dumps({"edits": [
                {"path": "utf8.txt", "replacements": [{"old": "alpha", "new": "beta", "expectedOccurrences": 1}]},
                {"path": "utf16.txt", "replacements": [{"old": "alpha", "new": "beta", "expectedOccurrences": 1}]}
            ]}))

            FileSystemPatchEngine(root).execute(request, check=False)

            self.assertEqual(utf8_target.read_bytes(), b"\xef\xbb\xbfbeta")
            self.assertEqual(utf16_target.read_bytes(), b"\xff\xfe" + "beta".encode("utf-16-le"))

    def test_edit_accepts_crlf_anchor_for_lf_file_without_rewriting_line_endings(self) -> None:
        """Treat CRLF patch anchors as equivalent to LF file boundaries."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.txt"
            target.write_bytes(b"alpha\nbeta\ngamma\n")
            request = parse_patch_request(json.dumps({"edits": [{
                "path": "target.txt",
                "replacements": [{
                    "old": "alpha\r\nbeta",
                    "new": "alpha\r\ndelta",
                    "expectedOccurrences": 1,
                }],
            }]}))

            FileSystemPatchEngine(root).execute(request, check=False)

            self.assertEqual(target.read_bytes(), b"alpha\ndelta\ngamma\n")

    def test_edit_accepts_lf_anchor_for_crlf_file_without_rewriting_line_endings(self) -> None:
        """Treat LF patch anchors as equivalent to CRLF file boundaries."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.txt"
            target.write_bytes(b"alpha\r\nbeta\r\ngamma\r\n")
            request = parse_patch_request(json.dumps({"edits": [{
                "path": "target.txt",
                "replacements": [{
                    "old": "alpha\nbeta",
                    "new": "alpha\ndelta",
                    "expectedOccurrences": 1,
                }],
            }]}))

            FileSystemPatchEngine(root).execute(request, check=False)

            self.assertEqual(target.read_bytes(), b"alpha\r\ndelta\r\ngamma\r\n")

    def test_newline_equivalence_preserves_occurrence_guard(self) -> None:
        """Reject newline-equivalent anchors when their logical count is wrong."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.txt"
            target.write_bytes(b"alpha\nbeta\nalpha\nbeta\n")
            request = parse_patch_request(json.dumps({"edits": [{
                "path": "target.txt",
                "replacements": [{
                    "old": "alpha\r\nbeta",
                    "new": "changed",
                    "expectedOccurrences": 1,
                }],
            }]}))

            with self.assertRaisesRegex(PatchExecutionError, "Exact occurrence guard failed"):
                FileSystemPatchEngine(root).execute(request, check=True)

    def test_move_operation_moves_file_safely(self) -> None:
        """Safely move source file to absent destination target."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            source.write_text("hello move", encoding="utf-8")
            request = parse_patch_request(json.dumps({"moves": [{"fromPath": "source.txt", "toPath": "dest.txt"}]}))

            result = FileSystemPatchEngine(root).execute(request, check=False)

            self.assertFalse(source.exists())
            dest = root / "dest.txt"
            self.assertTrue(dest.exists())
            self.assertEqual(dest.read_text(encoding="utf-8"), "hello move")
            self.assertEqual(result.files[0].operation.value, "move")

    def test_move_operation_rejects_existing_destination(self) -> None:
        """Reject move when destination target already exists."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            source.write_text("source", encoding="utf-8")
            dest = root / "dest.txt"
            dest.write_text("dest", encoding="utf-8")
            request = parse_patch_request(json.dumps({"moves": [{"fromPath": "source.txt", "toPath": "dest.txt"}]}))

            with self.assertRaisesRegex(PatchExecutionError, "already exists"):
                FileSystemPatchEngine(root).execute(request, check=False)

    def test_delete_operation_removes_file_safely(self) -> None:
        """Safely delete existing target file."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "delete_me.txt"
            target.write_text("content to remove", encoding="utf-8")
            request = parse_patch_request(json.dumps({"deletes": [{"path": "delete_me.txt"}]}))

            result = FileSystemPatchEngine(root).execute(request, check=False)

            self.assertFalse(target.exists())
            self.assertEqual(result.files[0].operation.value, "delete")

    def test_delete_operation_rejects_non_existent_file(self) -> None:
        """Reject delete when target file does not exist."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = parse_patch_request(json.dumps({"deletes": [{"path": "non_existent.txt"}]}))

            with self.assertRaisesRegex(PatchExecutionError, "does not exist"):
                FileSystemPatchEngine(root).execute(request, check=False)

    def test_transient_dir_fallback_and_custom(self) -> None:
        """Verify transient_dir resolution falls back to workspace $agent/tmp/patches_rollback."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fallback = get_transient_dir(workspace_root=root)
            self.assertTrue(str(fallback).casefold().endswith(str(Path("$agent/tmp/patches_rollback")).casefold()))

    def test_later_commit_failure_rolls_back_edits_creates_moves_and_deletes(self) -> None:
        """Restore earlier commits (including deleted and moved files) after a transaction failure."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            to_edit = root / "edit.txt"
            to_edit.write_text("before", encoding="utf-8")
            to_delete = root / "delete.txt"
            to_delete.write_text("deleted content", encoding="utf-8")
            to_move = root / "move_src.txt"
            to_move.write_text("moved content", encoding="utf-8")

            request = parse_patch_request(json.dumps({
                "edits": [{"path": "edit.txt", "replacements": [{"old": "before", "new": "after", "expectedOccurrences": 1}]}],
                "deletes": [{"path": "delete.txt"}],
                "moves": [{"fromPath": "move_src.txt", "toPath": "move_dst.txt"}],
                "creates": [{"path": "new.txt", "content": "created"}]
            }))

            def fail_on_create(source: Path, destination: Path) -> None:
                """Fail when attempting to commit the create operation."""
                if destination.name == "new.txt":
                    raise OSError("simulated create commit failure")
                source.replace(destination)

            with self.assertRaises(PatchExecutionError) as raised:
                FileSystemPatchEngine(root, fail_on_create).execute(request, check=False)

            self.assertEqual(raised.exception.rollback, "completed")
            self.assertEqual(to_edit.read_text(encoding="utf-8"), "before")
            self.assertTrue(to_delete.exists())
            self.assertEqual(to_delete.read_text(encoding="utf-8"), "deleted content")
            self.assertTrue(to_move.exists())
            self.assertFalse((root / "move_dst.txt").exists())
            self.assertFalse((root / "new.txt").exists())


if __name__ == "__main__":
    unittest.main()
