# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Disk-free unit tests for the standalone new-agent seed factory."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

UTILITY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(UTILITY_ROOT))
sys.path.insert(0, str(UTILITY_ROOT.parents[1] / "brain" / "src"))

import create_agent_directory as factory  # noqa: E402
from brain.application.knowledge.models.dtos.runtime_config import BrainConfigsDTO  # noqa: E402
from create_agent_directory import (  # noqa: E402
    CORE_SEED_EXCLUDED_ROOT_NAMES,
    PRIVATE_STORE_NAMES,
    PUBLIC_SCREEN_NAMES,
    SYNC_AGENT_FILE_NAMES,
    SYNC_ROOT_NAMES,
    UTILITY_SYNC_FILES,
    _SyncStats,
    _copy_core_seed,
    _copy_ignore,
    create_agent_directory,
    default_brain_config,
    default_picture_config,
    normalize_agent_name,
    parse_cli_args,
    update_agent,
)


class CreateAgentDirectoryTests(unittest.TestCase):
    """Validate factory orchestration without materializing filesystem state."""

    @patch.object(Path, "write_text", autospec=True)
    @patch.object(Path, "mkdir", autospec=True)
    @patch.object(Path, "exists", autospec=True, return_value=False)
    @patch.object(factory, "_publish_seed")
    @patch.object(factory, "_create_agent_consumer")
    @patch.object(factory, "_write_publication_files")
    @patch.object(factory, "_sync_agent_prompt")
    @patch.object(factory, "_create_agent_authored_structure")
    @patch.object(factory, "_create_empty_core_state")
    @patch.object(factory, "_write_agent_configuration")
    @patch.object(factory, "_copy_core_seed")
    @patch.object(factory, "_validate_seed_sources")
    def test_create_agent_directory_orchestrates_seed_without_disk_writes(
        self,
        validate_seed_sources: MagicMock,
        copy_core_seed: MagicMock,
        write_agent_configuration: MagicMock,
        create_empty_core_state: MagicMock,
        create_agent_authored_structure: MagicMock,
        sync_agent_prompt: MagicMock,
        write_publication_files: MagicMock,
        create_agent_consumer: MagicMock,
        publish_seed: MagicMock,
        path_exists: MagicMock,
        path_mkdir: MagicMock,
        path_write_text: MagicMock,
    ) -> None:
        """Verify seed orchestration through mocked filesystem boundaries."""
        parent = Path("D:/agents")
        source_core = Path("D:/source-core")
        template = Path("D:/templates/AGENTS.md")
        final_root = parent.resolve() / "@Nova_1"
        temporary_root = parent.resolve() / ".@Nova_1.creating-fixture"
        create_agent_consumer.return_value = final_root / "$agent" / "scripts" / "brain.py"

        with patch.object(factory.uuid, "uuid4", return_value=SimpleNamespace(hex="fixture")):
            result = create_agent_directory(
                parent,
                "@Nova_1",
                "Alex",
                source_core=source_core,
                instruction_template=template,
            )

        self.assertEqual(result.agent_name, "@Nova_1")
        self.assertEqual(result.user_name, "Alex")
        self.assertEqual(Path(result.agent_root), final_root)
        self.assertEqual(Path(result.core_root), final_root / "core")
        self.assertEqual(Path(result.consumer_entrypoint), final_root / "$agent" / "scripts" / "brain.py")
        self.assertEqual(Path(result.license_path), final_root / "LICENSE")
        self.assertEqual(Path(result.readme_path), final_root / "README.md")
        self.assertEqual(len(result.configs), 3)
        self.assertEqual(len(result.stores), len(PRIVATE_STORE_NAMES))

        path_exists.assert_called_once_with(final_root)
        path_mkdir.assert_has_calls(
            [
                call(parent.resolve(), parents=True, exist_ok=True),
                call(temporary_root),
            ],
        )
        validate_seed_sources.assert_called_once_with(
            canonical_core=source_core.resolve(),
            instruction_template=template.resolve(),
            license_template=factory.LICENSE_TEMPLATE,
        )
        copy_core_seed.assert_called_once_with(source_core.resolve(), temporary_root / "core")
        write_agent_configuration.assert_called_once_with(
            agent_root=temporary_root,
            final_agent_root=final_root,
            agent_name="Nova_1",
            user_name="Alex",
        )
        create_empty_core_state.assert_called_once_with(
            temporary_root / "core",
            source_core=source_core.resolve(),
        )
        create_agent_authored_structure.assert_called_once_with(temporary_root)
        sync_agent_prompt.assert_called_once_with(
            template=template.resolve(),
            destination=temporary_root / "core" / "AGENTS.md",
            agent_name="Nova_1",
            user_name="Alex",
        )
        write_publication_files.assert_called_once_with(
            agent_root=temporary_root,
            readme_source=source_core.resolve() / "README.md",
        )
        create_agent_consumer.assert_called_once_with(agent_root=final_root)
        path_write_text.assert_called_once_with(
            temporary_root / ".gitignore",
            factory.AGENT_ROOT_GITIGNORE,
            encoding="utf-8",
        )
        publish_seed.assert_called_once_with(temporary_root, final_root)

    def test_default_picture_config_is_a_generic_disabled_mockup(self) -> None:
        """Validate provider-neutral picture defaults without reading or writing files."""
        picture_config = default_picture_config()

        self.assertEqual(picture_config["guidance"], {"tags": {}, "characters": {}})
        self.assertFalse(picture_config["image_model"]["enabled"])
        self.assertEqual(picture_config["image_model"]["api_key"], "$VISION_API_KEY")
        serialized = json.dumps(picture_config).casefold()
        for live_value in ("configured_character", "configured_tag"):
            self.assertNotIn(live_value, serialized)

        generated = default_brain_config(Path("D:/agents/@Example"), "Example", "Developer")
        validated = BrainConfigsDTO.model_validate(generated)
        self.assertEqual(validated.pictures.guidance.tags, {})
        self.assertEqual(validated.pictures.guidance.characters, {})
        self.assertFalse(validated.pictures.image_model.enabled)

    @patch.object(Path, "exists", autospec=True, return_value=True)
    def test_existing_destination_is_never_overwritten(self, path_exists: MagicMock) -> None:
        """Reject an occupied destination before invoking any write boundary."""
        parent = Path("D:/agents")

        with patch.object(factory, "_validate_seed_sources") as validate_seed_sources:
            with self.assertRaises(FileExistsError):
                create_agent_directory(parent, "Nova", "Alex")

        path_exists.assert_called_once_with(parent.resolve() / "@Nova")
        validate_seed_sources.assert_not_called()

    def test_cli_accepts_normalized_and_compatibility_flags(self) -> None:
        """Parse creation and update arguments as a pure command contract."""
        args = parse_cli_args(["D:/Agents", "--agent_name", "@Nova", "--user_name", "Alex"])
        self.assertEqual(args.command, "create-agent")
        self.assertEqual(normalize_agent_name(args.agent_name), "Nova")
        self.assertEqual(args.user_name, "Alex")

        update_args = parse_cli_args(["update-agent", "D:/Agents/@Nova", "--json"])
        self.assertEqual(update_args.command, "update-agent")
        self.assertEqual(update_args.path, "D:/Agents/@Nova")

    @patch.object(factory, "_sync_agent_prompt")
    @patch.object(factory, "_read_agent_identity", return_value=("Nova", "Alex"))
    @patch.object(factory, "_sync_publication_files")
    @patch.object(factory, "_sync_allowlisted_utilities")
    @patch.object(factory, "_sync_code_tree")
    @patch.object(factory, "_validate_update_sources")
    @patch.object(factory, "_resolve_existing_agent")
    def test_update_agent_aggregates_mocked_sync_boundaries(
        self,
        resolve_existing_agent: MagicMock,
        validate_update_sources: MagicMock,
        sync_code_tree: MagicMock,
        sync_allowlisted_utilities: MagicMock,
        sync_publication_files: MagicMock,
        read_agent_identity: MagicMock,
        sync_agent_prompt: MagicMock,
    ) -> None:
        """Aggregate update results without copying or deleting real filesystem entries."""
        source_core = Path("D:/source-core").resolve()
        agent_root = Path("D:/agents/@Nova").resolve()
        target_core = agent_root / "core"
        resolve_existing_agent.return_value = (agent_root, target_core)
        sync_code_tree.side_effect = [
            _SyncStats(copied_files=1, unchanged_files=2, removed_files=3),
            _SyncStats(copied_files=4, created_directories=5),
            _SyncStats(unchanged_files=6, removed_directories=7),
        ]
        sync_allowlisted_utilities.return_value = _SyncStats(copied_files=2, unchanged_files=3)
        sync_publication_files.return_value = _SyncStats(copied_files=8, unchanged_files=9)
        sync_agent_prompt.return_value = _SyncStats(copied_files=1)

        result = update_agent(agent_root, source_core=source_core)

        validate_update_sources.assert_called_once_with(source_core, target_core)
        self.assertEqual(
            sync_code_tree.call_args_list,
            [
                call(source=source_core / root_name, destination=target_core / root_name)
                for root_name in SYNC_ROOT_NAMES
            ],
        )
        sync_allowlisted_utilities.assert_called_once_with(
            source_core=source_core,
            target_core=target_core,
        )
        sync_publication_files.assert_called_once_with(
            agent_root=agent_root,
            readme_source=source_core / "README.md",
        )
        read_agent_identity.assert_called_once_with(agent_root)
        sync_agent_prompt.assert_called_once_with(
            template=source_core / "utilities" / "create_agent_directory" / "templates" / "AGENTS.md",
            destination=target_core / "AGENTS.md",
            agent_name="Nova",
            user_name="Alex",
        )
        self.assertEqual(
            result.updated_roots,
            [*SYNC_ROOT_NAMES, "utilities/documentation_utils", *factory.PUBLIC_PROFILE_ROOT_NAMES, "utilities"],
        )
        self.assertEqual(result.updated_files, [*SYNC_AGENT_FILE_NAMES, *UTILITY_SYNC_FILES])
        self.assertEqual(result.copied_files, 16)
        self.assertEqual(result.unchanged_files, 20)
        self.assertEqual(result.removed_files, 3)
        self.assertEqual(result.created_directories, 5)
        self.assertEqual(result.removed_directories, 7)

    @patch.object(factory, "_run_brain_lifecycle")
    def test_create_consumer_delegates_to_cloned_core_cli_without_disk_writes(
        self,
        run_lifecycle: MagicMock,
    ) -> None:
        """Invoke `create-brain` through the cloned agent's own core factory."""
        agent_root = Path("D:/agents/@Nova")

        launcher = factory._create_agent_consumer(agent_root=agent_root)

        self.assertEqual(launcher, agent_root / "$agent" / "scripts" / "brain.py")
        run_lifecycle.assert_called_once_with(
            command=[
                sys.executable,
                str(agent_root / "core" / "core_cli.py"),
                "create-brain",
                str(agent_root),
                "--json",
            ],
            cwd=agent_root,
            operation="create-brain",
        )

    @patch.object(factory, "_run_brain_lifecycle")
    @patch.object(Path, "is_file", autospec=True, return_value=True)
    def test_update_initializes_existing_consumer_without_disk_writes(
        self,
        path_is_file: MagicMock,
        run_lifecycle: MagicMock,
    ) -> None:
        """Invoke `init` through the updated agent's consumer launcher."""
        agent_root = Path("D:/agents/@Nova")
        launcher = agent_root / "$agent" / "scripts" / "brain.py"

        factory._initialize_agent_consumer(agent_root=agent_root)

        path_is_file.assert_called_once_with(launcher)
        run_lifecycle.assert_called_once_with(
            command=[sys.executable, str(launcher), "init", "--json"],
            cwd=agent_root,
            operation="init",
        )

    def test_copy_ignore_excludes_transient_and_generated_entries(self) -> None:
        """Keep transient trees out of clones through the pure ignore callback."""
        ignored = _copy_ignore(
            "D:/source-core/brain_explorer",
            [".tmp", "node_modules", "cache.pyc", "runtime.py"],
        )
        wiki_ignored = _copy_ignore(
            "D:/source-core/brain/documentation",
            ["wiki", "README.md"],
        )

        self.assertEqual(ignored, {".tmp", "node_modules", "cache.pyc"})
        self.assertEqual(wiki_ignored, {"wiki"})
        self.assertEqual(CORE_SEED_EXCLUDED_ROOT_NAMES, {"AGENTS.md"})

    @patch.object(factory.shutil, "copy2")
    @patch.object(Path, "is_dir", autospec=True, return_value=False)
    @patch.object(Path, "iterdir", autospec=True)
    @patch.object(Path, "mkdir", autospec=True)
    def test_core_seed_excludes_the_source_agent_template_without_disk_writes(
        self,
        path_mkdir: MagicMock,
        path_iterdir: MagicMock,
        path_is_dir: MagicMock,
        copy_file: MagicMock,
    ) -> None:
        """Keep the source identity template outside a cloned core seed."""
        source = Path("D:/source-core")
        destination = Path("D:/clone/core")
        source_prompt = source / "AGENTS.md"
        source_entrypoint = source / "core_cli.py"
        path_iterdir.return_value = iter((source_prompt, source_entrypoint))

        _copy_core_seed(source=source, destination=destination)

        path_mkdir.assert_called_once_with(destination, parents=True)
        path_is_dir.assert_called_once_with(source_entrypoint)
        copy_file.assert_called_once_with(source_entrypoint, destination / "core_cli.py")

    @patch.object(factory, "_validate_update_sources")
    @patch.object(factory, "_resolve_existing_agent")
    def test_update_agent_refuses_to_update_its_source_core(
        self,
        resolve_existing_agent: MagicMock,
        validate_update_sources: MagicMock,
    ) -> None:
        """Reject self-synchronization before any update boundary executes."""
        source_core = Path("D:/source-core").resolve()
        resolve_existing_agent.return_value = (source_core.parent, source_core)

        with self.assertRaisesRegex(ValueError, "onto itself"):
            update_agent(source_core, source_core=source_core)

        validate_update_sources.assert_not_called()


if __name__ == "__main__":
    unittest.main()
