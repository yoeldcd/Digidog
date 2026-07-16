# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Focused tests for extracted first-level brain architecture modules."""

from __future__ import annotations

# Standard Libraries Imports
import sys
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

# Application Modules Imports
from brain.application.logs.parsing import log_read_command, parse_entry, to_slug
from brain.application.memory.markdown_sections import extract_from_markdown, update_markdown
from brain.application.querying.source_refs import source_ref_from_path
from brain.infrastructure.vectorstores.chunking import chunk_dated_markdown_entries, markdown_header_slug, normalized_entry_time


class ArchitectureRefactorBoundaryTests(unittest.TestCase):
    """Verify extracted helper modules preserve their public behavior."""

    def test_logs_parsing_helpers_preserve_domain_and_reader_commands(self) -> None:
        """Ensure log parsing helpers keep canonical command and slug behavior."""
        domain, title, git_type = parse_entry(
            timestamp="06-07-2026 08:30 pm",
            body_text="### (`brain.application.logs`) [Precise Log]\n  **Type:**\n    fix\n",
        )

        self.assertEqual(domain, "brain.application.logs")
        self.assertEqual(title, "Precise Log")
        self.assertEqual(git_type, "fix")
        self.assertEqual(to_slug("v1.2 experimental"), "v1-2-experimental")
        self.assertEqual(log_read_command("06-07-2026", "06-07-2026 08:30 pm"), "read-log -d 06-07-2026 --time 20:30")

    def test_memory_markdown_sections_extract_and_update_list_items(self) -> None:
        """Ensure Markdown section extraction remains independent from filesystem writes."""
        content = "- **tone**: warm\n- **focus**:\n  architecture\n  tests\n"

        self.assertEqual(extract_from_markdown(content, "tone"), "warm")
        self.assertEqual(extract_from_markdown(content, "focus"), "architecture\n  tests")

        updated_content = update_markdown(content, "tone", "precise")
        self.assertIn("- **tone**: precise", updated_content)
        deleted_content = update_markdown(updated_content, "tone", None)
        self.assertNotIn("tone", deleted_content)

    def test_query_source_refs_preserve_reader_commands(self) -> None:
        """Ensure extracted source references still infer user-facing CLI readers."""
        profile_ref = source_ref_from_path(path="memory/profiles/developer/1 - instructions.md")
        diary_ref = source_ref_from_path(path="memory/diary/2026-07/06-07-2026.md", entry_time="20:30")

        self.assertEqual(profile_ref.read_command, "read-profile developer")
        self.assertEqual(diary_ref.read_command, "read-diary -d 06-07-2026 --time 20:30")
        self.assertEqual(profile_ref.domain, "profiles.developer.1 - instructions")

    def test_vector_chunking_preserves_dated_entry_metadata(self) -> None:
        """Ensure dated entries still chunk by body while keeping reader metadata."""
        chunks = chunk_dated_markdown_entries(
            category="diary",
            key="06-07-2026",
            content="## 06-07-2026 08:30 pm - Refactor\nBody text\n",
            mtime=123.0,
            path="memory/diary/2026-07/06-07-2026.md",
            source_kind="diary",
            reader_command="read-diary",
        )

        self.assertEqual(len(chunks), 1)
        chunk_id, body, metadata = chunks[0]
        self.assertEqual(chunk_id, "diary.06-07-2026#06-07-2026-08-30-pm-refactor")
        self.assertEqual(body, "Body text")
        self.assertEqual(metadata["entry_time"], "20:30")
        self.assertEqual(metadata["read_command"], "read-diary -d 06-07-2026 --time 20:30")
        self.assertEqual(normalized_entry_time("06-07-2026 08:30 pm - Refactor"), "20:30")
        self.assertEqual(markdown_header_slug("## Index"), "index")


if __name__ == "__main__":
    unittest.main()
