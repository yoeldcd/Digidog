# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Regression tests for the Brain CLI presentation boundary."""

from __future__ import annotations

import importlib
import inspect
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


class CliCleanArchitectureTest(unittest.TestCase):
    """Verify command metadata and executable actions stay separated."""

    def test_command_modules_only_expose_metadata(self) -> None:
        """Ensure registered command modules do not expose executable handlers."""
        registry = importlib.import_module("brain.presentation.commands.registry")

        for command_module in registry.COMMAND_MODULES:
            with self.subTest(command_module=command_module.__name__):
                self.assertTrue(hasattr(command_module, "SCHEMA"))
                self.assertFalse(hasattr(command_module, "handle"))

    def test_action_registry_has_handler_for_each_command_schema(self) -> None:
        """Ensure every registered command schema declares one lazy executable action."""
        command_registry = importlib.import_module("brain.presentation.commands.registry")
        action_registry = importlib.import_module("brain.presentation.actions.registry")

        command_names = {command_module.SCHEMA.name for command_module in command_registry.COMMAND_MODULES}
        action_names = set(action_registry.ACTION_HANDLERS)

        self.assertEqual(command_names, action_names)
        for command_name, module_path in action_registry.ACTION_HANDLERS.items():
            with self.subTest(command_name=command_name):
                self.assertIsInstance(module_path, str)
                self.assertTrue(module_path.startswith("brain.presentation.actions."))
        self.assertTrue(callable(action_registry.get_action_handler(command_name="log-index")))

    def test_action_registry_does_not_import_command_registry(self) -> None:
        """Ensure executable routing does not consume command schema metadata at import time."""
        script = (
            "import sys; "
            f"sys.path.insert(0, {str(SOURCE_ROOT)!r}); "
            "import brain.presentation.actions.registry; "
            "print('brain.presentation.commands.registry' in sys.modules)"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertEqual(result.stdout.strip(), "False")

    def test_cli_entrypoint_delegates_parser_and_dispatch(self) -> None:
        """Ensure `brain.cli` stays a thin entrypoint without parser or dispatch ownership."""
        cli_module = importlib.import_module("brain.cli")

        self.assertFalse(hasattr(cli_module, "build_parser"))
        self.assertFalse(hasattr(cli_module, "handle_command"))
        self.assertTrue(hasattr(cli_module, "main"))

    def test_parser_owns_hidden_no_speak_runtime_flag(self) -> None:
        """Ensure technical voice suppression stays outside command schemas."""
        from brain.presentation.commands.registry import COMMAND_MODULES
        from brain.presentation.parser.services.argument_parser_service import build_argument_parser

        parser = build_argument_parser(COMMAND_MODULES)
        args = parser.parse_args(["--no-speak", "list-profiles"])

        self.assertTrue(args.no_speak)
        list_profiles = next(module.SCHEMA for module in COMMAND_MODULES if module.SCHEMA.name == "list-profiles")
        self.assertFalse(any("--no-speak" in argument.flags for argument in list_profiles.arguments))

    def test_every_command_parser_accepts_json_output(self) -> None:
        """Ensure the parser supplies `--json` even when a command has no native JSON schema."""
        from brain.presentation.commands.registry import COMMAND_MODULES
        from brain.presentation.parser.services.argument_parser_service import build_argument_parser

        parser = build_argument_parser(COMMAND_MODULES)
        subparsers_action = next(action for action in parser._actions if action.dest == "command")

        for command_module in COMMAND_MODULES:
            with self.subTest(command=command_module.SCHEMA.name):
                command_parser = subparsers_action.choices[command_module.SCHEMA.name]
                option_strings = {
                    option
                    for action in command_parser._actions
                    for option in action.option_strings
                }
                self.assertIn("--json", option_strings)

    def test_avatar_message_routes_to_the_enriched_presentation_command(self) -> None:
        """Keep the avatar-facing name bound to the visual and spoken message flow."""
        from brain.presentation.commands.registry import COMMAND_MODULES
        from brain.presentation.parser.services.argument_parser_service import build_argument_parser

        parser = build_argument_parser(COMMAND_MODULES)
        args = parser.parse_args(["avatar-message", "# Hola", "--emotion", "happy"])

        self.assertEqual(args.command, "speak")
        self.assertEqual(args.body, "# Hola")
        self.assertEqual(args.emotion, "happy")

        stdin_args = parser.parse_args(["avatar-message", "--stdin-json", "--json"])
        self.assertTrue(stdin_args.stdin_json)
        self.assertTrue(stdin_args.json)

    def test_query_messages_flag_selects_persisted_messages(self) -> None:
        """Keep the convenience flag equivalent to the explicit messages source."""
        from brain.presentation.actions.general.command_query import _resolve_query_source
        from brain.presentation.commands.registry import COMMAND_MODULES
        from brain.presentation.parser.services.argument_parser_service import build_argument_parser

        parser = build_argument_parser(COMMAND_MODULES)
        args = parser.parse_args(["query", "first words", "--messages", "--json"])

        self.assertTrue(args.messages)
        self.assertEqual(_resolve_query_source(args), "messages")

    def test_avatar_service_uses_the_public_service_command_names(self) -> None:
        """Expose the avatar lifecycle without voice-daemon command terminology."""
        from brain.presentation.commands.registry import COMMAND_MODULES

        command_names = {module.SCHEMA.name for module in COMMAND_MODULES}
        self.assertTrue(
            {"start-avatar-service", "stop-avatar-service", "avatar-service-status"} <= command_names
        )
        self.assertTrue(
            {"start-speak-daemon", "stop-speak-daemon", "speak-daemon-status"}.isdisjoint(command_names)
        )

    def test_core_utilities_have_dedicated_brain_commands(self) -> None:
        """Expose core-owned utilities without routing consumers through snippets."""
        from brain.presentation.actions.registry import get_action_handler
        from brain.presentation.commands.registry import COMMAND_MODULES

        command_names = {module.SCHEMA.name for module in COMMAND_MODULES}
        self.assertTrue({"wiki", "propagate-agent-prompt"} <= command_names)
        self.assertTrue(callable(get_action_handler(command_name="wiki")))
        self.assertTrue(callable(get_action_handler(command_name="propagate-agent-prompt")))

    def test_text_commands_declare_semantic_json_payloads(self) -> None:
        """Ensure commands without native serializers explicitly construct domain payloads."""
        from brain.presentation.actions.registry import get_action_handler
        from brain.presentation.commands.registry import COMMAND_MODULES

        for command_module in COMMAND_MODULES:
            schema = command_module.SCHEMA
            has_native_json = any("--json" in argument.flags for argument in schema.arguments)
            if has_native_json:
                continue
            with self.subTest(command=schema.name):
                handler = get_action_handler(command_name=schema.name)
                self.assertIsNotNone(handler)
                self.assertIn("json_payload", inspect.getsource(handler))

    def test_dispatch_rejects_legacy_text_without_semantic_payload(self) -> None:
        """Ensure JSON mode cannot silently embed a command's rendered text."""
        from brain.presentation.router.services.command_router_service import dispatch_command

        def text_action(_args: Namespace) -> int:
            print("legacy output")
            return 0

        stdout = StringIO()
        args = Namespace(command="legacy", json=True, no_speak=False)
        with patch(
            "brain.presentation.router.services.command_router_service.get_action_handler",
            return_value=text_action,
        ), redirect_stdout(stdout):
            exit_code = dispatch_command(args)

        self.assertEqual(exit_code, 1)
        self.assertEqual(
            __import__("json").loads(stdout.getvalue()),
            {
                "ok": False,
                "command": "legacy",
                "error": "Command did not provide a semantic JSON payload.",
            },
        )

    def test_dispatch_serializes_action_semantic_payload(self) -> None:
        """Ensure a migrated action emits its domain fields instead of captured prose."""
        from brain.presentation.router.services.command_router_service import dispatch_command

        def semantic_action(args: Namespace) -> int:
            print("human-only rendering")
            args.json_payload = {
                "ok": True,
                "command": "show-backlog",
                "count": 1,
                "tasks": [{"id": "t1", "status": "TODO"}],
            }
            return 0

        stdout = StringIO()
        args = Namespace(command="show-backlog", json=True, no_speak=False)
        with patch(
            "brain.presentation.router.services.command_router_service.get_action_handler",
            return_value=semantic_action,
        ), redirect_stdout(stdout):
            exit_code = dispatch_command(args)

        payload = __import__("json").loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertNotIn("output", payload)
        self.assertEqual(payload["tasks"], [{"id": "t1", "status": "TODO"}])

    def test_dispatch_preserves_native_json_payload(self) -> None:
        """Ensure existing structured command payloads are not nested in a generic envelope."""
        from brain.presentation.router.services.command_router_service import dispatch_command

        def json_action(_args: Namespace) -> int:
            print('{"ok": true, "items": [1]}')
            return 0

        stdout = StringIO()
        args = Namespace(command="native", json=True, no_speak=False)
        with patch(
            "brain.presentation.router.services.command_router_service.get_action_handler",
            return_value=json_action,
        ), redirect_stdout(stdout):
            exit_code = dispatch_command(args)

        self.assertEqual(exit_code, 0)
        self.assertEqual(__import__("json").loads(stdout.getvalue()), {"ok": True, "items": [1]})

    def test_init_delegates_log_migration_to_update_log_index(self) -> None:
        """Ensure init consumes update-log-index instead of duplicating log migration."""
        command_init = importlib.import_module("brain.presentation.actions.general.command_init")
        source_text = inspect.getsource(command_init.handle)

        self.assertIn("command_update_log_index.handle", source_text)
        self.assertNotIn("migrate_log_files_to_database", source_text)
        self.assertNotIn("migrate_legacy_log_files_to_database", source_text)

    def test_query_log_domain_resolution_falls_back_by_levels(self) -> None:
        """Ensure Query Log resolves overqualified and suffix domain paths."""
        from brain.application.logs.query_service import resolve_query_log_domain

        domains = ["cli", "brain.infrastructure.explorer", "brain_explorer.layout"]

        self.assertEqual(resolve_query_log_domain("brain.cli", domains), "cli")
        self.assertEqual(resolve_query_log_domain("infrastructure.explorer", domains), "brain.infrastructure.explorer")
        self.assertEqual(resolve_query_log_domain("brain_explorer", domains), "brain_explorer")
        self.assertEqual(resolve_query_log_domain("unknown.domain", domains), "unknown.domain")

    def test_complete_work_rejects_stage_paths_outside_workspace(self) -> None:
        """Ensure atomic completion cannot stage paths beyond its workspace."""
        from brain.presentation.actions.general.command_complete_work import _validated_stage_paths

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir).resolve()
            owned_file = workspace_root / "owned.txt"
            owned_file.write_text("owned", encoding="utf-8")

            self.assertEqual(_validated_stage_paths(workspace_root, ["owned.txt"]), ["owned.txt"])
            with self.assertRaises(ValueError):
                _validated_stage_paths(workspace_root, ["../outside.txt"])


if __name__ == "__main__":
    unittest.main()
