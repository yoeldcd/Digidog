# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Regression tests for the Brain Explorer CLI facade and server helpers."""

from __future__ import annotations

# Standard Libraries Imports
from http import HTTPStatus
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

# Application Modules Imports
from brain.infrastructure.explorer.cli_facade import BrainCliFacade, CliCommandResult
from brain.infrastructure.explorer.server import (
    ApiRouteError,
    BrainExplorerRequestHandler,
    parse_prompt_command,
    resolve_static_file,
    resolve_workspace_picture,
)
from brain.infrastructure.explorer.validation import resolve_registered_workspace_root
from brain.infrastructure.runtime.paths import get_agent_home, get_core_root


class BrainExplorerTests(unittest.TestCase):
    """Verify Brain Explorer command registration and safe helpers."""

    def test_serve_explorer_command_is_registered(self) -> None:
        """Ensure the CLI command schema and lazy action handler stay aligned."""
        from brain.presentation.actions.registry import get_action_handler
        from brain.presentation.commands.registry import COMMAND_MODULES

        command_names = {command_module.SCHEMA.name for command_module in COMMAND_MODULES}

        self.assertIn("serve-explorer", command_names)
        self.assertTrue(callable(get_action_handler(command_name="serve-explorer")))

    def test_static_file_resolution_rejects_path_traversal(self) -> None:
        """Ensure static serving cannot escape the configured dist directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            dist_dir = Path(temp_dir) / "dist"
            dist_dir.mkdir()

            with self.assertRaises(ValueError):
                resolve_static_file(dist_dir=dist_dir, request_path="/../secret.txt")

    def test_static_file_resolution_defaults_to_index(self) -> None:
        """Ensure the root URL maps to the explorer index file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            dist_dir = Path(temp_dir) / "dist"
            dist_dir.mkdir()

            self.assertEqual(resolve_static_file(dist_dir=dist_dir, request_path="/"), dist_dir / "index.html")

    def test_workspace_picture_resolution_accepts_only_safe_filenames(self) -> None:
        """Ensure log attachment routes cannot resolve a path outside pictures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            pictures_dir = Path(temp_dir) / "pictures"
            pictures_dir.mkdir()

            self.assertEqual(
                resolve_workspace_picture(pictures_dir=pictures_dir, picture_name="log-reference.png"),
                pictures_dir / "log-reference.png",
            )
            with self.assertRaises(ValueError):
                resolve_workspace_picture(pictures_dir=pictures_dir, picture_name="../secret.png")

    def test_voice_file_resolution_rejects_path_traversal(self) -> None:
        """Ensure stored voice playback cannot escape the dialogue directory."""
        handler = object.__new__(BrainExplorerRequestHandler)

        self.assertIsNone(handler._resolve_voice_file(filename="../secret.mp3"))
        self.assertIsNone(handler._resolve_voice_file(filename="message.wav"))

    def test_backlog_route_requests_complete_task_tree(self) -> None:
        """Ensure Explorer does not hide the durable completed backlog projection."""
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            calls.append({"arguments": arguments, "stdin_text": stdin_text, "expect_json": expect_json})
            return CliCommandResult(True, ["fake", *arguments], 0, "tree", "", 1, None)

        handler._run_cli = fake_run
        result = handler._backlog({})

        self.assertTrue(result["ok"])
        self.assertEqual(calls[0]["arguments"], ["show-backlog", "--all", "--json"])
        self.assertTrue(calls[0]["expect_json"])

    def test_global_query_route_uses_deep_without_removed_response_flag(self) -> None:
        """Ensure Explorer honors the current global-query CLI contract."""
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            calls.append({"arguments": arguments, "stdin_text": stdin_text, "expect_json": expect_json})
            return CliCommandResult(True, ["fake", *arguments], 0, "{}", "", 1, {})

        handler._run_cli = fake_run
        result = handler._global_query({"q": "Angi", "deep": "true", "response": "true"})

        self.assertTrue(result["ok"])
        self.assertIn("--deep", calls[0]["arguments"])
        self.assertNotIn("--response", calls[0]["arguments"])

    def test_voice_replay_route_delegates_named_message_to_daemon(self) -> None:
        """Ensure message PLAY reuses retained daemon audio instead of synthesis."""
        handler = object.__new__(BrainExplorerRequestHandler)
        handler._read_json_body = lambda: {"name": "14-07-26~11-00.mp3"}

        with patch("brain.infrastructure.explorer.routes.voice_routes.VoiceDaemonClient.replay", return_value={"replaying": True}) as replay:
            result = handler._voice_replay()

        self.assertTrue(result["ok"])
        replay.assert_called_once_with(name="14-07-26~11-00.mp3")

    def test_cli_facade_parses_json_output(self) -> None:
        """Ensure successful JSON command output is parsed into `data`."""
        facade = BrainCliFacade(timeout=2.0)

        result = facade.run(arguments=["list-profiles", "--json"], expect_json=True)

        self.assertTrue(result.ok)
        self.assertIsInstance(result.data, dict)

    def test_cli_facade_suppresses_voice_for_internal_commands(self) -> None:
        """Ensure every Explorer invocation carries the parser-only silence flag."""
        from unittest.mock import patch

        captured_arguments = []

        def fake_run_cli(argv):
            captured_arguments.extend(argv)
            print("{}")
            return 0

        facade = BrainCliFacade(timeout=2.0)
        with patch("brain.infrastructure.explorer.cli_facade.run_cli", side_effect=fake_run_cli):
            result = facade.run(arguments=["list-profiles", "--json"], expect_json=True)

        self.assertTrue(result.ok)
        self.assertEqual(captured_arguments, ["--no-speak", "list-profiles", "--json"])
        self.assertNotIn("--no-speak", result.command)

    def test_cli_facade_reports_malformed_json(self) -> None:
        """Ensure invalid JSON from a command is returned as an API error."""
        facade = BrainCliFacade(timeout=2.0)

        result = facade.run(arguments=["show-backlog"], expect_json=True)

        self.assertFalse(result.ok)
        self.assertEqual(result.code, 0)
        self.assertIn("Invalid JSON", result.error)

    def test_cli_facade_restores_process_streams(self) -> None:
        """Ensure in-process execution does not leak redirected standard streams."""
        facade = BrainCliFacade(timeout=2.0)
        stdin_before = sys.stdin

        facade.run(arguments=["show-backlog"], expect_json=False)

        self.assertIs(sys.stdin, stdin_before)

    def test_workspace_context_is_idempotent_and_nestable(self) -> None:
        """Ensure repeated WoSP selection preserves one stable process context."""
        facade = BrainCliFacade()
        original_root = facade.workspace_root
        original_env = os.environ.get("WORKSPACE_ROOT")

        with facade.workspace_context(original_root):
            first_value = os.environ.get("WORKSPACE_ROOT")
            with facade.workspace_context(original_root):
                self.assertEqual(os.environ.get("WORKSPACE_ROOT"), first_value)
                self.assertEqual(facade.workspace_root, original_root)

        self.assertEqual(facade.workspace_root, original_root)
        self.assertEqual(os.environ.get("WORKSPACE_ROOT"), original_env)

    def test_workspace_switch_changes_only_local_consumer_context(self) -> None:
        """Keep global core and agent identity stable while selecting a mirror."""
        facade = BrainCliFacade()
        original_core = get_core_root()
        original_agent = get_agent_home()
        with tempfile.TemporaryDirectory() as directory:
            mirror_root = Path(directory).resolve()
            with facade.workspace_context(mirror_root):
                self.assertEqual(get_core_root(), original_core)
                self.assertEqual(get_agent_home(), original_agent)
                self.assertEqual(os.environ.get("WORKSPACE_ROOT"), str(mirror_root))

    def test_workspace_selection_is_limited_to_agent_mirrors(self) -> None:
        """Reject Explorer requests for workspaces outside the core registry."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registered = root / "registered"
            unregistered = root / "unregistered"
            registered.mkdir()
            unregistered.mkdir()
            mirrors_file = root / "brain_mirrors.json"
            mirrors_file.write_text(
                json.dumps([{"name": "Registered", "path": str(registered)}]),
                encoding="utf-8",
            )
            with patch(
                "brain.infrastructure.explorer.validation.get_brain_mirrors_path",
                return_value=mirrors_file,
            ):
                self.assertEqual(resolve_registered_workspace_root(registered), registered.resolve())
                with self.assertRaises(ApiRouteError) as context:
                    resolve_registered_workspace_root(unregistered)
            self.assertEqual(context.exception.status, HTTPStatus.FORBIDDEN)

    def test_prompt_command_parsing_strips_facade_prefix(self) -> None:
        """Ensure prompt parsing returns argv tokens without a shell or facade prefix."""
        arguments = parse_prompt_command("brain.py knowledge-show --scope global --entities --json")

        self.assertEqual(arguments, ["knowledge-show", "--scope", "global", "--entities", "--json"])

    def test_cli_prompt_executes_allowlisted_vector(self) -> None:
        """Ensure the prompt route executes allowlisted commands as argv vectors."""
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)
        handler._read_json_body = lambda: {"command": "memory-structure --json"}

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            calls.append({"arguments": arguments, "stdin_text": stdin_text, "expect_json": expect_json})
            return CliCommandResult(
                ok=True,
                command=["fake", *arguments],
                code=0,
                stdout="{}",
                stderr="",
                duration_ms=1,
                data={"ok": True},
            )

        handler._run_cli = fake_run

        result = handler._cli_prompt()

        self.assertTrue(result.ok)
        self.assertEqual(calls[0]["arguments"], ["memory-structure", "--json"])
        self.assertTrue(calls[0]["expect_json"])

    def test_cli_prompt_rejects_mutating_commands(self) -> None:
        """Ensure the prompt route does not execute mutation commands."""
        handler = object.__new__(BrainExplorerRequestHandler)
        handler._read_json_body = lambda: {"command": "set-memory-entry notes.x value --json"}

        with self.assertRaises(ApiRouteError):
            handler._cli_prompt()

    def test_log_index_delegates_optional_domain(self) -> None:
        """Ensure the Explorer log index route consumes the semantic JSON schema."""
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            calls.append({"arguments": arguments, "stdin_text": stdin_text, "expect_json": expect_json})
            return CliCommandResult(
                ok=True,
                command=["fake", *arguments],
                code=0,
                stdout='{"ok": true, "entries": []}\n',
                stderr="",
                duration_ms=1,
                data={"ok": True, "entries": []},
            )

        handler._run_cli = fake_run

        result = handler._log_index({"domain": "brain_explorer"})

        self.assertTrue(result["ok"])
        self.assertEqual(calls[0]["arguments"], ["log-index", "brain_explorer", "--json"])
        self.assertTrue(calls[0]["expect_json"])

    def test_backlog_task_add_delegates_bounded_command(self) -> None:
        """Ensure backlog task creation maps to an allowlisted CLI vector."""
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)
        handler._read_json_body = lambda: {
            "action": "add",
            "domain": "brain_explorer.ui",
            "title": "Fix product UI",
            "description": "Replace raw CLI panes with focused layouts.",
            "priority": "high",
        }

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            calls.append({"arguments": arguments, "stdin_text": stdin_text, "expect_json": expect_json})
            return CliCommandResult(
                ok=True,
                command=["fake", *arguments],
                code=0,
                stdout="added\n",
                stderr="",
                duration_ms=1,
                data=None,
            )

        handler._run_cli = fake_run

        result = handler._backlog_task()

        self.assertTrue(result["ok"])
        self.assertEqual(
            calls[0]["arguments"],
            [
                "add-task",
                "brain_explorer.ui",
                "Fix product UI",
                "-d",
                "Replace raw CLI panes with focused layouts.",
                "-p",
                "HIGH",
                "--json",
            ],
        )
        self.assertTrue(calls[0]["expect_json"])

    def test_backlog_task_status_delegates_explicit_state(self) -> None:
        """Ensure state changes use the bounded generic status command."""
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)
        handler._read_json_body = lambda: {"action": "working", "taskId": "#t42"}

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            calls.append({"arguments": arguments, "stdin_text": stdin_text, "expect_json": expect_json})
            return CliCommandResult(
                ok=True,
                command=["fake", *arguments],
                code=0,
                stdout="done\n",
                stderr="",
                duration_ms=1,
                data=None,
            )

        handler._run_cli = fake_run

        result = handler._backlog_task()

        self.assertTrue(result["ok"])
        self.assertEqual(calls[0]["arguments"], ["set-task-status", "t42", "WORKING", "--json"])
        self.assertTrue(calls[0]["expect_json"])

    def test_backlog_task_finish_remains_a_done_status_compatibility_action(self) -> None:
        """Ensure existing Explorer callers can still finish a task safely."""
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)
        handler._read_json_body = lambda: {"action": "finish", "taskId": "t42"}

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            calls.append({"arguments": arguments, "stdin_text": stdin_text, "expect_json": expect_json})
            return CliCommandResult(True, ["fake", *arguments], 0, "done", "", 1, None)

        handler._run_cli = fake_run

        result = handler._backlog_task()

        self.assertTrue(result["ok"])
        self.assertEqual(calls[0]["arguments"], ["set-task-status", "t42", "DONE", "--json"])

    def test_backlog_task_delete_only_forwards_force_when_requested(self) -> None:
        """Ensure the force escape hatch remains an explicit bounded flag."""
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)
        handler._read_json_body = lambda: {"action": "delete", "taskId": "t42", "force": True}

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            calls.append({"arguments": arguments, "stdin_text": stdin_text, "expect_json": expect_json})
            return CliCommandResult(True, ["fake", *arguments], 0, "deleted", "", 1, None)

        handler._run_cli = fake_run

        result = handler._backlog_task()

        self.assertTrue(result["ok"])
        self.assertEqual(calls[0]["arguments"], ["delete-task", "t42", "--force", "--json"])
        self.assertTrue(calls[0]["expect_json"])


if __name__ == "__main__":
    unittest.main()
