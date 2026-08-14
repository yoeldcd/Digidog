# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Exercise the Brain Explorer CLI facade and server-helper regression contract.

The suite verifies filesystem safety, route delegation, voice handling, workspace isolation, and
process-level CLI protections without changing the production behavior under test.
"""

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

# Import-path guard: make source modules addressable when this test file runs directly.

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

# Application Modules Imports
from brain.infrastructure.explorer.cli_facade import BrainCliFacade, CliCommandResult
from brain.infrastructure.explorer.resources import (
    build_live_wiki_manifest,
    find_wiki_markdown_files,
    resolve_workspace_image,
)
from brain.infrastructure.explorer.server import (
    ApiRouteError,
    BrainExplorerRequestHandler,
    parse_prompt_command,
    resolve_static_file,
    resolve_workspace_picture,
)
from brain.infrastructure.explorer.validation import resolve_registered_workspace_root
from brain.infrastructure.runtime.paths import get_agent_home, get_core_root
from brain.infrastructure.messages.models import MessageRecordDTO
from brain.infrastructure.voice.contracts.avatar_speak_request import AvatarSpeakRequest


class BrainExplorerTests(unittest.TestCase):
    """Verify Brain Explorer registration, routing boundaries, and facade invariants.

    Covers the domain guarantees that keep workspace files, voice playback, and delegated CLI calls
    isolated while preserving the public Explorer contracts exercised by the UI.
    """

    def test_serve_explorer_command_is_registered(self) -> None:
        """Ensure the CLI command schema and lazy action handler stay aligned.

        Protects command discoverability so the Explorer entry point cannot diverge between registry
        metadata and the handler that is resolved at runtime.

        Args:
            None.

        Returns:
            None.
        """
        from brain.presentation.actions.registry import get_action_handler
        from brain.presentation.commands.registry import COMMAND_MODULES

        command_names = {command_module.SCHEMA.name for command_module in COMMAND_MODULES}

        self.assertIn("serve-explorer", command_names)
        self.assertTrue(callable(get_action_handler(command_name="serve-explorer")))

    def test_live_wiki_manifest_reads_markdown_without_generated_artifacts(self) -> None:
        """Verify that project documentation is the live Wiki contract.

        Keeps generated wiki artifacts out of the manifest so the Explorer reflects source Markdown
        files and their stable navigation metadata.

        Args:
            None.

        Returns:
            None.
        """

        # Fixture boundary: isolate live documentation discovery from the actual project tree.

        # Fixture boundary: isolate default-index resolution from any real build output.

        # Fixture boundary: provide a disposable pictures root for containment checks.

        # Fixture boundary: build both an in-workspace image and an external local image.

        # Fixture boundary: create representative safe-root, external, missing, and directory cases.

        with tempfile.TemporaryDirectory() as temp_dir:
            documentation_dir = Path(temp_dir) / "sample_project" / "documentation"
            documentation_dir.mkdir(parents=True)
            (documentation_dir / "README.md").write_text("# Live project docs\n", encoding="utf-8")
            generated_dir = documentation_dir / "wiki"
            generated_dir.mkdir()
            (generated_dir / "stale.md").write_text("# Ignore me\n", encoding="utf-8")

            files = find_wiki_markdown_files(documentation_dir)
            manifest = build_live_wiki_manifest(documentation_dir)

            self.assertEqual(files, [documentation_dir / "README.md"])
            self.assertEqual(manifest["projectName"], "sample_project")
            self.assertEqual(manifest["pages"], [{
                "id": "readme",
                "title": "Home",
                "icon": "\U0001F3E0",
                "source": "README.md",
                "sourceHref": "../README.md",
            }])
            self.assertEqual(manifest["virtualPages"], [])

    def test_static_file_resolution_rejects_path_traversal(self) -> None:
        """Ensure static serving cannot escape the configured dist directory.

        Enforces the route invariant that a request path must remain inside the configured frontend
        asset root before any file can be served.

        Args:
            None.

        Returns:
            None.
        """

        # Fixture boundary: create a disposable asset root for traversal validation.

        with tempfile.TemporaryDirectory() as temp_dir:
            dist_dir = Path(temp_dir) / "dist"
            dist_dir.mkdir()

            # Security assertion: traversal input must be rejected before path resolution escapes.

            with self.assertRaises(ValueError):
                resolve_static_file(dist_dir=dist_dir, request_path="/../secret.txt")

    def test_static_file_resolution_defaults_to_index(self) -> None:
        """Ensure the root URL maps to the explorer index file.

        Preserves the frontend entry-point invariant that an empty route resolves to index.html under
        the selected distribution directory.

        Args:
            None.

        Returns:
            None.
        """

        # Fixture boundary: isolate index fallback resolution from filesystem state.

        with tempfile.TemporaryDirectory() as temp_dir:
            dist_dir = Path(temp_dir) / "dist"
            dist_dir.mkdir()

            self.assertEqual(resolve_static_file(dist_dir=dist_dir, request_path="/"), dist_dir / "index.html")

    def test_workspace_picture_resolution_accepts_only_safe_filenames(self) -> None:
        """Ensure log attachment routes cannot escape the pictures directory.

        Verifies that a safe filename is accepted while a traversal reference remains outside the
        route's permitted picture root and is rejected.

        Args:
            None.

        Returns:
            None.
        """

        # Fixture boundary: isolate picture-name containment from filesystem state.

        with tempfile.TemporaryDirectory() as temp_dir:
            pictures_dir = Path(temp_dir) / "pictures"
            pictures_dir.mkdir()

            self.assertEqual(
                resolve_workspace_picture(pictures_dir=pictures_dir, picture_name="log-reference.png"),
                pictures_dir / "log-reference.png",
            )

            # Security assertion: traversal must not resolve to a file outside the picture root.

            with self.assertRaises(ValueError):
                resolve_workspace_picture(pictures_dir=pictures_dir, picture_name="../secret.png")

    def test_workspace_image_resolution_accepts_supported_local_reference_forms(self) -> None:
        """Accept supported workspace and absolute local image references.

        Confirms that the resolver normalizes the supported reference forms to canonical local paths
        without broadening the allowed image surface.

        Args:
            None.

        Returns:
            None.
        """

        # Fixture boundary: isolate supported image reference normalization from real workspace state.

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            workspace = temp_root / "workspace"
            workspace_image = workspace / "$agent" / "pictures" / "reference image.png"
            workspace_image.parent.mkdir(parents=True)
            workspace_image.write_bytes(b"png")
            outside_image = temp_root / "outside image.jpg"
            outside_image.write_bytes(b"jpg")

            expected_paths = {
                "$agent/pictures/reference image.png": workspace_image.resolve(),
                outside_image.as_uri(): outside_image.resolve(),
                str(outside_image).replace("/", "\\"): outside_image.resolve(),
            }

            # Reference matrix: every supported spelling must converge on its canonical path.

            for reference, expected_path in expected_paths.items():
                self.assertEqual(resolve_workspace_image(workspace, reference), expected_path)

    def test_workspace_image_resolution_rejects_unsafe_references(self) -> None:
        """Reject traversal, network, missing, and non-image references.

        Protects the image route from path escape, unsupported URI forms, absent files, directories,
        and extensions that do not represent image content.

        Args:
            None.

        Returns:
            None.
        """

        # Fixture boundary: isolate unsafe image reference rejection from real workspace state.

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            workspace = temp_root / "workspace"
            workspace.mkdir()
            outside_image = temp_root / "outside.png"
            outside_image.write_bytes(b"png")
            outside_text = temp_root / "secret.txt"
            outside_text.write_text("secret", encoding="utf-8")
            image_directory = temp_root / "directory.png"
            image_directory.mkdir()

            unsafe_references = (
                "$agent/../../outside.png",
                r"\\server\share\image.png",
                "file://server/share/image.png",
                "file://localhost/C:/image.png",
                "file:/C:/image.png",
                str(outside_text),
                str(temp_root / "missing.png"),
                str(image_directory),
                "$agent/pictures/document.txt",
            )

            # Rejection matrix: every unsafe reference must fail closed with the same domain error.

            for reference in unsafe_references:

                # Exception contract: reject each unsafe reference before it can reach file serving.

                with self.assertRaises(ValueError):
                    resolve_workspace_image(workspace, reference)

            pictures_dir = workspace / "$agent" / "pictures"
            pictures_dir.mkdir(parents=True)
            symlink_path = pictures_dir / "escape.png"

            # Symlink probe: verify that a picture link cannot escape the workspace containment rule.

            try:
                symlink_path.symlink_to(outside_image)

            # Platform boundary: tolerate systems that cannot create symlinks in the test fixture.

            except (OSError, NotImplementedError):
                symlink_path = None

            # Symlink assertion: only an actually created escape link needs rejection validation.

            if symlink_path is not None:

                # Security assertion: a symlinked image must not bypass canonical containment checks.

                with self.assertRaises(ValueError):
                    resolve_workspace_image(workspace, "$agent/pictures/escape.png")

    def test_workspace_image_route_preserves_not_found_for_missing_files(self) -> None:
        """Keep missing local images as the route's existing 404 response.

        Verifies that a missing asset reaches the established not-found payload and is not forwarded
        to the picture sender as if a readable file existed.

        Args:
            None.

        Returns:
            None.
        """
        responses = []
        handler = object.__new__(BrainExplorerRequestHandler)

        # Response spy callback: capture the route status and payload without opening a network socket.

        handler._send_json = lambda status, payload: responses.append((status, payload))

        # Sender guard callback: fail if a missing image is incorrectly treated as a served file.

        handler._send_picture_file = lambda picture_file: self.fail("Missing image must not be sent.")

        # Fixture boundary: run the route against an isolated workspace with no requested image.

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)

            # Workspace patch: bind route lookup to the disposable fixture root.

            # Registry patch: direct validation to the disposable mirror manifest.

            with patch(
                "brain.infrastructure.explorer.routes.resource_routes.get_workspace_root",
                return_value=workspace,
            ):
                handler._handle_workspace_image("GET", {"path": "$agent/pictures/missing.png"})

        self.assertEqual(responses, [(
            HTTPStatus.NOT_FOUND,
            {"ok": False, "error": "Image not found."},
        )])

    def test_voice_file_resolution_rejects_path_traversal(self) -> None:
        """Ensure stored voice playback cannot escape the dialogue directory.

        Confirms that only valid retained audio names can resolve, keeping replay requests inside the
        server-owned dialogue storage boundary.

        Args:
            None.

        Returns:
            None.
        """
        handler = object.__new__(BrainExplorerRequestHandler)

        self.assertIsNone(handler._resolve_voice_file(filename="../secret.mp3"))
        self.assertIsNone(handler._resolve_voice_file(filename="message.wav"))

    def test_backlog_route_requests_complete_task_tree(self) -> None:
        """Ensure Explorer requests the complete durable backlog projection.

        Protects the UI contract that backlog reads include completed tasks and use the canonical JSON
        command vector rather than a reduced or transient view.

        Args:
            None.

        Returns:
            None.
        """
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            """Capture a backlog CLI request and return a successful result.

            Preserves the delegation boundary so the test can inspect the exact durable projection
            requested by the route without invoking the live CLI.

            Args:
                arguments: Delegated command arguments.
                stdin_text: Optional delegated standard input.
                expect_json: Whether the caller expects JSON output.

            Returns:
                Successful synthetic CLI result.
            """
            calls.append({"arguments": arguments, "stdin_text": stdin_text, "expect_json": expect_json})

            return CliCommandResult(True, ["fake", *arguments], 0, "tree", "", 1, None)

        handler._run_cli = fake_run
        result = handler._backlog({})

        self.assertTrue(result["ok"])
        self.assertEqual(calls[0]["arguments"], ["show-backlog", "--all", "--json"])
        self.assertTrue(calls[0]["expect_json"])

    def test_global_query_route_uses_deep_without_removed_response_flag(self) -> None:
        """Ensure Explorer honors the current global-query CLI contract.

        Verifies that deep search remains explicit while a removed response flag is not reintroduced
        into the allowlisted argument vector.

        Args:
            None.

        Returns:
            None.
        """
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            """Capture a global query request and return JSON output.

            Records the normalized command vector while returning structured data so only route
            argument construction is under test.

            Args:
                arguments: Delegated command arguments.
                stdin_text: Optional delegated standard input.
                expect_json: Whether the caller expects JSON output.

            Returns:
                Successful synthetic CLI result.
            """
            calls.append({"arguments": arguments, "stdin_text": stdin_text, "expect_json": expect_json})

            return CliCommandResult(True, ["fake", *arguments], 0, "{}", "", 1, {})

        handler._run_cli = fake_run
        result = handler._global_query({"q": "Nova", "deep": "true", "response": "true"})

        self.assertTrue(result["ok"])
        self.assertIn("--deep", calls[0]["arguments"])
        self.assertNotIn("--response", calls[0]["arguments"])

    def test_knowledge_deltas_route_aggregates_all_physical_scopes(self) -> None:
        """Ensure Explorer aggregates the UI's all-scope delta review.

        Confirms that the aggregate response preserves physical scope identity and combines candidate
        identifiers from each underlying knowledge store.

        Args:
            None.

        Returns:
            None.
        """
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            """Return scope-specific knowledge delta data.

            Supplies deterministic per-scope rows so aggregation can be verified independently of the
            persistent knowledge stores and their current contents.

            Args:
                arguments: Delegated command arguments.
                stdin_text: Optional delegated standard input.
                expect_json: Whether the caller expects JSON output.

            Returns:
                Successful synthetic CLI result.
            """
            calls.append(arguments)
            scope = arguments[arguments.index("--scope") + 1]
            data = {
                "review_rows": [{"id": 1 if scope == "global" else 2}],
                "candidate_ids": [1 if scope == "global" else 2],
                "blocked_ids": [],
            }

            return CliCommandResult(True, ["fake", *arguments], 0, json.dumps(data), "", 1, data)

        handler._run_cli = fake_run

        result = handler._knowledge_deltas(
            method="GET",
            query={"scope": "all", "limit": "80", "status": "pending"},
        )

        self.assertTrue(result["ok"])
        self.assertEqual([row["scope"] for row in result["data"]["review_rows"]], ["global", "local"])
        self.assertEqual(result["data"]["candidate_ids"], [1, 2])
        self.assertEqual(len(calls), 2)

    def test_knowledge_deltas_route_requires_physical_scope_for_apply(self) -> None:
        """Prevent ambiguous all-scope delta mutation requests.

        Enforces the mutation invariant that applying a knowledge delta must identify one physical
        store instead of silently choosing among global and local scopes.

        Args:
            None.

        Returns:
            None.
        """
        handler = object.__new__(BrainExplorerRequestHandler)

        # Mutation guard: an all-scope apply request must fail before any delegated write can occur.

        with self.assertRaises(ApiRouteError) as context:
            handler._knowledge_deltas(method="POST", query={"scope": "all"})

        self.assertEqual(context.exception.status, HTTPStatus.BAD_REQUEST)

    def test_global_query_route_accepts_messages_source(self) -> None:
        """Forward persisted messages as a first-class query source.

        Keeps persisted dialogue searchable through the same route contract as the other Brain data
        sources instead of treating messages as an implicit or unsupported source.

        Args:
            None.

        Returns:
            None.
        """
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            """Capture a messages query and return an empty result.

            Records source forwarding while returning a stable empty JSON list so only query routing
            is exercised.

            Args:
                arguments: Delegated command arguments.
                stdin_text: Optional delegated standard input.
                expect_json: Whether the caller expects JSON output.

            Returns:
                Successful synthetic CLI result.
            """
            calls.append(arguments)

            return CliCommandResult(True, ["fake", *arguments], 0, "[]", "", 1, [])

        handler._run_cli = fake_run
        result = handler._global_query({"q": "primeras palabras", "source": "messages"})

        self.assertTrue(result["ok"])
        self.assertIn("messages", calls[0])

    def test_voice_replay_route_delegates_named_message_to_daemon(self) -> None:
        """Ensure message playback reuses retained daemon audio.

        Protects the replay contract by forwarding the persisted filename to the daemon instead of
        synthesizing new audio or inferring playback state in the Explorer layer.

        Args:
            None.

        Returns:
            None.
        """
        handler = object.__new__(BrainExplorerRequestHandler)

        # Request callback: supply the retained audio identity without parsing an HTTP body.

        handler._read_json_body = lambda: {"name": "14-07-26~11-00.mp3"}

        # Daemon patch: observe replay delegation while keeping the test independent of audio hardware.

        # Voice patches: isolate repository lookup, workspace identity, and daemon enqueue behavior.

        with patch(
            "brain.infrastructure.explorer.routes.voice_routes.VoiceDaemonClient.replay",
            return_value={"replaying": True},
        ) as replay:
            result = handler._voice_replay()

        self.assertTrue(result["ok"])
        replay.assert_called_once_with(name="14-07-26~11-00.mp3")

    def test_voice_status_exposes_daemon_confirmed_playback_identity(self) -> None:
        """Ensure polling exposes daemon-confirmed playback identity.

        Verifies that the route returns the daemon's state and active speech identifier without local
        guesses that could drift from the actual playback process.

        Args:
            None.

        Returns:
            None.
        """
        handler = object.__new__(BrainExplorerRequestHandler)
        status = {"ok": True, "state": "speaking", "activeSpeakId": "speak-focused", "muted": False}

        # Daemon patch: provide authoritative playback state without contacting the voice service.

        with patch("brain.infrastructure.explorer.routes.voice_routes.VoiceDaemonClient.status", return_value=status):
            result = handler._voice_status()

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["state"], "speaking")
        self.assertEqual(result["data"]["activeSpeakId"], "speak-focused")

    def test_voice_synthesize_uses_persisted_message_contract(self) -> None:
        """Generate historical audio from server-owned persisted text.

        Ensures replay synthesis uses the persisted message record, consumer workspace, and voice
        metadata contract rather than client-supplied text or inferred identity.

        Args:
            None.

        Returns:
            None.
        """
        handler = object.__new__(BrainExplorerRequestHandler)

        # Request callback: provide the persisted message identifier used by the replay route.

        handler._read_json_body = lambda: {"messageId": "speak-history"}
        record = MessageRecordDTO(
            id="speak-history",
            created_at="2026-07-17T01:30:00+03:00",
            text="Mensaje historico.",
            emotion="calm",
            chat_id="chat-1",
            language="es",
        )
        consumer_root = Path("D:/registered-consumer").resolve()

        # Persistence patch: supply the historical record while preserving consumer workspace identity.

        with patch(
            "brain.infrastructure.explorer.routes.voice_routes.MessageRepository.get_message",
            return_value=record,
        ), patch(
            "brain.infrastructure.explorer.routes.voice_routes.get_workspace_root",
            return_value=consumer_root,
        ), patch("brain.infrastructure.explorer.routes.voice_routes.VoiceDaemonClient.speak") as speak:
            result = handler._voice_synthesize()

        self.assertTrue(result["ok"])
        self.assertTrue(result["data"]["queued"])
        speak.assert_called_once_with(
            AvatarSpeakRequest(
                text="Mensaje historico.",
                display_text="Mensaje historico.",
                lang="es",
                emotion="calm",
                consumer_path=str(consumer_root),
                codex_thread_id="chat-1",
                source_command="historical-message-audio",
                source_phase="replay",
            ),
        )

    def test_cli_facade_parses_json_output(self) -> None:
        """Ensure successful JSON command output is parsed into data.

        Confirms that a successful delegated command exposes structured payload data while retaining
        the facade's public result contract.

        Args:
            None.

        Returns:
            None.
        """
        facade = BrainCliFacade(timeout=2.0)

        result = facade.run(arguments=["list-profiles", "--json"], expect_json=True)

        self.assertTrue(result.ok)
        self.assertIsInstance(result.data, dict)

    def test_cli_facade_applies_internal_runtime_flags(self) -> None:
        """Ensure internal calls are silent and use user authority.

        Protects the boundary between the public command identity and the internal runtime vector by
        requiring silence and explicit user authority only inside delegated execution.

        Args:
            None.

        Returns:
            None.
        """
        captured_arguments: list[str] = []

        def fake_run_cli(argv: list[str]) -> int:
            """Capture the exact internal argv delegated by Explorer.

            Records internal parser flags and emits valid JSON so the test can distinguish delegated
            runtime arguments from the sanitized public command representation.

            Args:
                argv: Internal argument vector.

            Returns:
                Successful synthetic exit code.
            """
            captured_arguments.extend(argv)
            print("{}")

            return 0

        facade = BrainCliFacade(timeout=2.0)

        # Runtime patch: observe the exact delegated vector without invoking the live command router.

        with patch("brain.infrastructure.explorer.cli_facade.run_cli", side_effect=fake_run_cli):
            result = facade.run(arguments=["list-profiles", "--json"], expect_json=True)

        self.assertTrue(result.ok)
        self.assertEqual(
            captured_arguments,
            [
                "--no-speak",
                "list-profiles",
                "--json",
                "--authority",
                "user",
            ],
        )
        self.assertNotIn("--no-speak", result.command)
        self.assertNotIn("--authority", result.command)

    def test_cli_facade_reports_malformed_json(self) -> None:
        """Ensure malformed command JSON becomes an API error.

        Verifies that command completion remains observable while invalid structured output is reported
        through the result error field instead of raising a parser exception to the route.

        Args:
            None.

        Returns:
            None.
        """
        facade = BrainCliFacade(timeout=2.0)

        result = facade.run(arguments=["show-backlog"], expect_json=True)

        self.assertFalse(result.ok)
        self.assertEqual(result.code, 0)
        self.assertIn("Invalid JSON", result.error)

    def test_cli_facade_restores_process_streams(self) -> None:
        """Ensure in-process execution restores redirected streams.

        Protects process-global stdin ownership so a request-local capture cannot leak into subsequent
        commands after the delegated call returns.

        Args:
            None.

        Returns:
            None.
        """
        facade = BrainCliFacade(timeout=2.0)
        stdin_before = sys.stdin

        facade.run(arguments=["show-backlog"], expect_json=False)

        self.assertIs(sys.stdin, stdin_before)

    def test_workspace_context_is_idempotent_and_nestable(self) -> None:
        """Ensure workspace context selection is idempotent and nestable.

        Confirms that repeated selection does not churn process state and that nested contexts restore
        the original workspace and environment exactly once.

        Args:
            None.

        Returns:
            None.
        """
        facade = BrainCliFacade()
        original_root = facade.workspace_root
        original_env = os.environ.get("WORKSPACE_ROOT")

        # Context fixture: activate the current root to exercise idempotent workspace selection.

        with facade.workspace_context(original_root):
            first_value = os.environ.get("WORKSPACE_ROOT")

            # Nested context clause: verify inherited state remains stable for the same target root.

            with facade.workspace_context(original_root):
                self.assertEqual(os.environ.get("WORKSPACE_ROOT"), first_value)
                self.assertEqual(facade.workspace_root, original_root)

        self.assertEqual(facade.workspace_root, original_root)
        self.assertEqual(os.environ.get("WORKSPACE_ROOT"), original_env)

    def test_workspace_switch_changes_only_local_consumer_context(self) -> None:
        """Keep global identity stable while selecting a workspace mirror.

        Verifies that a consumer workspace changes only the facade's local context and environment,
        leaving core and agent identity resolution anchored to the global installation.

        Args:
            None.

        Returns:
            None.
        """
        facade = BrainCliFacade()
        original_core = get_core_root()
        original_agent = get_agent_home()

        # Fixture boundary: create a disposable mirror root for consumer-context selection.

        # Fixture boundary: create registered and unregistered roots with an isolated registry file.

        with tempfile.TemporaryDirectory() as directory:
            mirror_root = Path(directory).resolve()

            # Context fixture: activate the mirror while observing global identity invariants.

            with facade.workspace_context(mirror_root):
                self.assertEqual(get_core_root(), original_core)
                self.assertEqual(get_agent_home(), original_agent)
                self.assertEqual(os.environ.get("WORKSPACE_ROOT"), str(mirror_root))

    def test_workspace_selection_is_limited_to_agent_mirrors(self) -> None:
        """Reject workspaces outside the configured mirror registry.

        Enforces the route boundary that only registered agent mirrors may become active consumer
        workspaces, preventing arbitrary filesystem roots from being selected.

        Args:
            None.

        Returns:
            None.
        """

        # Fixture boundary: compare registered and unregistered roots within a disposable mirror registry.

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

            # Registry patch: redirect mirror authorization to the disposable manifest.

            with patch(
                "brain.infrastructure.explorer.validation.get_brain_mirrors_path",
                return_value=mirrors_file,
            ):
                self.assertEqual(resolve_registered_workspace_root(registered), registered.resolve())

                # Authorization assertion: an unregistered root must fail before activation.

                with self.assertRaises(ApiRouteError) as context:
                    resolve_registered_workspace_root(unregistered)
            self.assertEqual(context.exception.status, HTTPStatus.FORBIDDEN)

    def test_prompt_command_parsing_strips_facade_prefix(self) -> None:
        """Ensure prompt parsing strips shell and facade prefixes.

        Confirms that prompt input becomes a clean argv vector without preserving a shell executable
        or the facade script name as a delegated command argument.

        Args:
            None.

        Returns:
            None.
        """
        arguments = parse_prompt_command("brain.py knowledge-show --scope global --entities --json")

        self.assertEqual(arguments, ["knowledge-show", "--scope", "global", "--entities", "--json"])

    def test_cli_prompt_executes_allowlisted_vector(self) -> None:
        """Ensure the prompt route executes an allowlisted argv vector.

        Protects the prompt boundary by inspecting the normalized arguments and structured-output mode
        passed to the route's CLI callback.

        Args:
            None.

        Returns:
            None.
        """
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)

        # Request callback: provide an allowlisted prompt command without parsing an HTTP body.

        handler._read_json_body = lambda: {"command": "memory-structure --json"}

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            """Capture an allowlisted prompt request.

            Records the route's bounded argv vector and returns a deterministic payload without
            invoking the real Brain CLI.

            Args:
                arguments: Delegated command arguments.
                stdin_text: Optional delegated standard input.
                expect_json: Whether the caller expects JSON output.

            Returns:
                Successful synthetic CLI result.
            """
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
        """Ensure the prompt route rejects mutation commands.

        Preserves the read-only prompt invariant by stopping mutating command names before they can
        reach the delegated CLI callback.

        Args:
            None.

        Returns:
            None.
        """
        handler = object.__new__(BrainExplorerRequestHandler)

        # Request callback: supply a known mutation command to exercise the rejection boundary.

        handler._read_json_body = lambda: {"command": "set-memory-entry notes.x value --json"}

        # Mutation assertion: reject the command before any execution path is entered.

        with self.assertRaises(ApiRouteError):
            handler._cli_prompt()

    def test_log_index_delegates_optional_domain(self) -> None:
        """Ensure the log index route delegates an optional domain.

        Confirms that a selected domain is preserved in the canonical JSON command while the route
        continues to request structured output.

        Args:
            None.

        Returns:
            None.
        """
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            """Capture a log index request.

            Records optional domain forwarding and returns the route's expected JSON shape without
            consulting the live log database.

            Args:
                arguments: Delegated command arguments.
                stdin_text: Optional delegated standard input.
                expect_json: Whether the caller expects JSON output.

            Returns:
                Successful synthetic CLI result.
            """
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
        """Ensure task creation maps to a bounded CLI vector.

        Protects task creation from arbitrary argument expansion by checking the exact normalized
        domain, description, priority, and JSON flags sent to the CLI.

        Args:
            None.

        Returns:
            None.
        """
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)

        # Request callback: provide validated task-creation fields without an HTTP parser.

        handler._read_json_body = lambda: {
            "action": "add",
            "domain": "brain_explorer.ui",
            "title": "Fix product UI",
            "description": "Replace raw CLI panes with focused layouts.",
            "priority": "high",
        }

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            """Capture a task creation request.

            Records the bounded command vector and returns deterministic success without writing to
            the real backlog.

            Args:
                arguments: Delegated command arguments.
                stdin_text: Optional delegated standard input.
                expect_json: Whether the caller expects JSON output.

            Returns:
                Successful synthetic CLI result.
            """
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
        """Ensure state changes delegate an explicit bounded status.

        Preserves the route's allowlisted task-state mapping so one command can update durable backlog
        state without exposing generic CLI argument construction.

        Args:
            None.

        Returns:
            None.
        """
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)

        # Request callback: provide an explicit status payload without parsing an HTTP body.

        handler._read_json_body = lambda: {"action": "working", "taskId": "#t42"}

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            """Capture a task status request.

            Preserves the bounded state payload so the test isolates delegation from task-storage behavior.

            Args:
                arguments: Delegated command arguments.
                stdin_text: Optional delegated standard input.
                expect_json: Whether the caller expects JSON output.

            Returns:
                Successful synthetic CLI result.
            """
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
        """Ensure finish remains a compatible DONE status action.

        Verifies the legacy finish action is translated into the canonical DONE state command so older
        Explorer clients retain their completion behavior.

        Args:
            None.

        Returns:
            None.
        """
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)

        # Request callback: provide the legacy finish action without parsing an HTTP body.

        handler._read_json_body = lambda: {"action": "finish", "taskId": "t42"}

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            """Capture a compatible task finish request.

            Preserves the legacy completion payload so the test isolates compatibility mapping from storage.

            Args:
                arguments: Delegated command arguments.
                stdin_text: Optional delegated standard input.
                expect_json: Whether the caller expects JSON output.

            Returns:
                Successful synthetic CLI result.
            """
            calls.append({"arguments": arguments, "stdin_text": stdin_text, "expect_json": expect_json})

            return CliCommandResult(True, ["fake", *arguments], 0, "done", "", 1, None)

        handler._run_cli = fake_run

        result = handler._backlog_task()

        self.assertTrue(result["ok"])
        self.assertEqual(calls[0]["arguments"], ["set-task-status", "t42", "DONE", "--json"])

    def test_backlog_task_delete_only_forwards_force_when_requested(self) -> None:
        """Ensure task deletion forwards force only when requested.

        Confirms deletion keeps the explicit force escape hatch bounded to a caller-provided boolean
        rather than forwarding arbitrary task-management flags.

        Args:
            None.

        Returns:
            None.
        """
        calls = []
        handler = object.__new__(BrainExplorerRequestHandler)

        # Request callback: provide the bounded deletion action without parsing an HTTP body.

        handler._read_json_body = lambda: {"action": "delete", "taskId": "t42", "force": True}

        def fake_run(arguments: list[str], stdin_text: str | None = None, expect_json: bool = True) -> CliCommandResult:
            """Capture a task deletion request.

            Preserves the bounded deletion payload so the test isolates force-flag forwarding from storage.

            Args:
                arguments: Delegated command arguments.
                stdin_text: Optional delegated standard input.
                expect_json: Whether the caller expects JSON output.

            Returns:
                Successful synthetic CLI result.
            """
            calls.append({"arguments": arguments, "stdin_text": stdin_text, "expect_json": expect_json})

            return CliCommandResult(True, ["fake", *arguments], 0, "deleted", "", 1, None)

        handler._run_cli = fake_run

        result = handler._backlog_task()

        self.assertTrue(result["ok"])
        self.assertEqual(calls[0]["arguments"], ["delete-task", "t42", "--force", "--json"])
        self.assertTrue(calls[0]["expect_json"])


# Script entrypoint: run unittest's CLI only when this module is executed directly.

if __name__ == "__main__":
    unittest.main()
