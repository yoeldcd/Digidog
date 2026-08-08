"""Focused contracts for the canonical ``registre-image`` command."""

from __future__ import annotations

import argparse
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from brain.presentation.actions.pictures.command_registre_image import handle
from brain.presentation.commands.pictures.command_registre_image import SCHEMA
from brain.presentation.commands.registry import COMMAND_MODULES
from brain.presentation.parser.services.argument_parser_service import build_argument_parser


class RegistreImageCommandTests(unittest.TestCase):
    """Validate parser exposure and action boundary behavior."""

    def test_schema_exposes_canonical_registration_parameters(self) -> None:
        """Ensure every requested image registration option is declared."""
        self.assertEqual(SCHEMA.name, "registre-image")
        flags = [flag for argument in SCHEMA.arguments for flag in argument.flags]
        self.assertIn("--image-file", flags)
        self.assertIn("--image-data", flags)
        self.assertIn("--scope", flags)
        self.assertIn("--domain", flags)
        self.assertIn("--description", flags)
        self.assertIn("--index", flags)
        self.assertIn("--json", flags)

    def test_parser_accepts_base64_contract(self) -> None:
        """Parse the canonical base64 form without losing dotted domains."""
        parser = build_argument_parser(COMMAND_MODULES)
        args = parser.parse_args(
            [
                "registre-image",
                "--image-data",
                "data:image/png;base64,AAAA",
                "--scope",
                "global",
                "--domain",
                "a.b.c",
                "--description",
                "A sample",
                "--index",
                "--json",
            ]
        )
        self.assertEqual(args.command, "registre-image")
        self.assertEqual(args.image_data, "data:image/png;base64,AAAA")
        self.assertEqual(args.scope, "global")
        self.assertEqual(args.domain, "a.b.c")
        self.assertTrue(args.index)

    def test_action_forwards_normalized_contract_and_renders_json(self) -> None:
        """Forward source, scope, domain, description, and index to the use case."""
        args = argparse.Namespace(
            image_file="",
            image_data="data:image/png;base64,AAAA",
            scope="LOCAL",
            domain=" a.b.c ",
            description="sample",
            index=True,
            json=True,
            color=False,
        )
        with patch(
            "brain.presentation.actions.pictures.command_registre_image.register_picture",
            return_value={"id": "picture-1", "relative_path": "a/b/image.png"},
        ) as register:
            with redirect_stdout(io.StringIO()) as stdout:
                exit_code = handle(args)

        self.assertEqual(exit_code, 0)
        register.assert_called_once_with(
            image_file="",
            image_data="data:image/png;base64,AAAA",
            scope="local",
            domain="a.b.c",
            description="sample",
            index=True,
        )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["command"], "registre-image")
        self.assertEqual(payload["picture"]["id"], "picture-1")

    def test_action_rejects_both_image_sources(self) -> None:
        """Prevent ambiguous invocations that provide file and base64 inputs."""
        args = argparse.Namespace(
            image_file="C:/tmp/image.png",
            image_data="AAAA",
            scope="local",
            domain="a.b",
            description="",
            index=False,
            json=True,
            color=False,
        )
        with redirect_stdout(io.StringIO()) as stdout:
            exit_code = handle(args)

        self.assertEqual(exit_code, 1)
        self.assertIn("exactly one", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
