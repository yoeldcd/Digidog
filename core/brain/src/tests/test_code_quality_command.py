"""Regression tests for the Brain code-quality adapter."""

from __future__ import annotations

import shlex
import sys
import unittest
from argparse import Namespace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from brain.presentation.commands.registry import COMMAND_MODULES
from brain.presentation.parser.services.argument_parser_service import (
    build_argument_parser,
)

SOURCE_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = SOURCE_ROOT.parents[1]

for import_root in (CORE_ROOT, SOURCE_ROOT):
    import_text = str(import_root)

    if import_text not in sys.path:
        sys.path.insert(0, import_text)

from brain.presentation.actions.utilities import command_code_quality


class CodeQualityCommandTest(unittest.TestCase):
    """Cover direct argument forwarding and compact adapter output."""

    def test_parser_and_registry(self) -> None:
        """Parse direct paths and resolve the registered lazy action.

        Args:
            No arguments are accepted.

        Returns:
            None: Assertions complete when parsing and registry resolution succeed.
        """
        from brain.presentation.actions.registry import get_action_handler

        parser = build_argument_parser(COMMAND_MODULES)
        args = parser.parse_args(
            [
                "code-quality",
                "src/a.py",
                "tests/test_a.py",
                "--mode",
                "check",
                "--json",
            ]
        )

        self.assertEqual(args.paths, ["src/a.py", "tests/test_a.py"])
        self.assertTrue(callable(get_action_handler("code-quality")))

    def test_launcher_receives_exact_arguments_for_every_mode(self) -> None:
        """Forward direct paths and flags without rebuilding Core semantics.

        Args:
            No arguments are accepted.

        Returns:
            None: Assertions complete when every mode forwards exactly.
        """

        cases = (
            (
                Namespace(
                    paths=["src/a.py"],
                    mode="check",
                    evaluator="",
                    language="",
                    schema="request",
                    json=True,
                ),
                ["src/a.py", "--mode", "check"],
            ),
            (
                Namespace(
                    paths=["src/a.ts"],
                    mode="format",
                    evaluator="strict",
                    language="typescript",
                    schema="request",
                    json=True,
                ),
                [
                    "src/a.ts",
                    "--mode",
                    "format",
                    "--evaluator",
                    "strict",
                    "--language",
                    "typescript",
                ],
            ),
            (
                Namespace(
                    paths=[],
                    mode="schema",
                    evaluator="",
                    language="",
                    schema="model",
                    json=True,
                ),
                ["--mode", "schema", "--schema", "model"],
            ),
        )

        for args, expected in cases:
            with self.subTest(mode=args.mode):

                def emit_payload(arguments: list[str]) -> int:
                    """Emit a compact successful launcher payload.

                    Args:
                        arguments: Forwarded launcher arguments.

                    Returns:
                        int: Successful launcher exit code.
                    """
                    print('{"status":"pass"}')

                    return 0

                with patch.object(
                    command_code_quality.code_quality_evaluator,
                    "main",
                    side_effect=emit_payload,
                ) as launcher:
                    self.assertEqual(command_code_quality.handle(args), 0)

                launcher.assert_called_once_with(expected)
                self.assertEqual(args.json_payload["command"], "code-quality")

    def test_payload_errors_are_source_redacted(self) -> None:
        """Reject malformed, multiple, and non-object launcher output.

        Args:
            No arguments are accepted.

        Returns:
            None: Assertions complete when malformed payloads are redacted.
        """

        cases = (
            ('{"status":"pass"}\n', 0),
            ("not-json\n", 2),
            ("{}\n{}\n", 2),
            ("[]\n", 2),
        )

        for output, expected_code in cases:
            with self.subTest(output=output):
                args = Namespace(
                    paths=[],
                    mode="schema",
                    evaluator="",
                    language="",
                    schema="request",
                    json=True,
                )

                def emit_output(
                    _arguments: list[str],
                    rendered_output: str = output,
                ) -> int:
                    """Emit one controlled launcher output for the adapter.

                    Args:
                        _arguments: Forwarded launcher arguments.
                        rendered_output: Payload text under test.

                    Returns:
                        int: Successful launcher exit code.
                    """
                    print(rendered_output, end="")

                    return 0

                with patch.object(
                    command_code_quality.code_quality_evaluator,
                    "main",
                    side_effect=emit_output,
                ):
                    self.assertEqual(
                        command_code_quality.handle(args),
                        expected_code,
                    )

                if expected_code == 2:
                    self.assertEqual(
                        args.json_payload,
                        {
                            "command": "code-quality",
                            "mode": "schema",
                            "status": "blocked",
                            "summary": "code quality evaluation failed",
                        },
                    )

    def test_real_check_and_format_use_relative_path_arguments(self) -> None:
        """Run Core through Brain without exposing check-mode source text.

        Args:
            No arguments are accepted.

        Returns:
            None: Assertions complete when check and format remain in-memory.
        """

        with TemporaryDirectory() as directory:
            workspace_root = Path(directory).resolve()
            source_path = workspace_root / "sample.py"
            source_path.write_text(
                '"""Sample module."""\n\nvalue: int = 1\n',
                encoding="utf-8",
            )

            for mode in ("check", "format"):
                args = Namespace(
                    paths=["sample.py"],
                    mode=mode,
                    evaluator="",
                    language="",
                    schema="request",
                    json=True,
                )

                with patch.object(
                    command_code_quality.code_quality_evaluator.Path,
                    "cwd",
                    return_value=workspace_root,
                ):
                    exit_code = command_code_quality.handle(args)

                self.assertEqual(exit_code, 0, args.json_payload)

                if mode == "check":
                    self.assertNotIn("content", repr(args.json_payload))
                    self.assertIn("summary", args.json_payload)
                    self.assertIn("files", args.json_payload)

                else:
                    self.assertIn("files", args.json_payload)

    def test_command_contract_documents_direct_path_boundary_and_languages(
        self,
    ) -> None:
        """Verify the command schema advertises supported suffixes and gates.

        Args:
            No arguments are accepted.

        Returns:
            None: Assertions complete when the schema is authoritative.
        """
        from brain.presentation.commands.utilities.command_code_quality import SCHEMA

        self.assertTrue(
            all(
                example.startswith("py {LOCAL_BRAIN_SCRIPT}")
                for example in SCHEMA.examples
            )
        )
        self.assertTrue(all("--json" in example for example in SCHEMA.examples))
        safeguards = " ".join(SCHEMA.safeguards)
        self.assertIn(".js/.mjs/.cjs", safeguards)
        self.assertIn(".ts/.tsx", safeguards)
        self.assertIn("stdin", SCHEMA.description.lower())
        output_text = " ".join(
            field.description
            for schema in SCHEMA.output_schemas
            for field in schema.fields
        )
        self.assertIn("blocks_aggregate", output_text)

        parser = build_argument_parser(COMMAND_MODULES)

        for example in SCHEMA.examples:
            tokens = shlex.split(example)
            command_index = tokens.index("code-quality")
            parsed = parser.parse_args(tokens[command_index:])
            self.assertEqual(parsed.command, "code-quality")


if __name__ == "__main__":
    unittest.main()
