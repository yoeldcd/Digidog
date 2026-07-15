"""Tests for the standalone new-agent seed factory."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

UTILITY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(UTILITY_ROOT))

from create_agent_directory import (  # noqa: E402
    create_agent_directory,
    normalize_agent_name,
    parse_cli_args,
    update_agent,
)


def _fake_core(root: Path) -> Path:
    core = root / "source-core"
    (core / "brain").mkdir(parents=True)
    (core / "brain_explorer" / "dist").mkdir(parents=True)
    (core / "utilities").mkdir()
    (core / "configs").mkdir()
    (core / "database").mkdir()
    (core / "assets" / "avatar").mkdir(parents=True)
    (core / "brain" / "documentation" / "wiki").mkdir(parents=True)
    (core / "brain" / "runtime.py").write_text("RUNTIME = True\n", encoding="utf-8")
    (core / "brain_explorer" / "dist" / "index.html").write_text("ok", encoding="utf-8")
    (core / "utilities" / "utility.py").write_text("UTILITY = True\n", encoding="utf-8")
    (core / "configs" / "personal.json").write_text("{}", encoding="utf-8")
    (core / "database" / "live.db").write_bytes(b"personal")
    (core / "assets" / "avatar" / "avatar_working.gif").write_bytes(b"GIF89a")
    (core / "assets" / "avatar" / "README.md").write_text("state contract\n", encoding="utf-8")
    (core / "assets" / "avatar" / "personal_portrait.png").write_bytes(b"private")
    (core / "brain" / "documentation" / "wiki" / "index.html").write_text("generated")
    (core / "requirements.txt").write_text("-r brain/requirements.txt\n", encoding="utf-8")
    (core / "core_cli.py").write_text(
        "from pathlib import Path\n"
        "HOME_ROOT = Path(__file__).resolve().parent\n"
        "CORE_ROOT = HOME_ROOT\n",
        encoding="utf-8",
    )
    return core


class CreateAgentDirectoryTests(unittest.TestCase):
    """Validate isolation, safety, and CLI normalization."""

    def test_create_agent_directory_clones_code_and_resets_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_core = _fake_core(root)
            result = create_agent_directory(
                root / "agents",
                "@Nova_1",
                "Alex",
                source_core=source_core,
                instruction_template=UTILITY_ROOT / "AGENT.md",
            )

            agent_root = Path(result.agent_root)
            self.assertEqual(agent_root.name, "@Nova_1")
            self.assertTrue((agent_root / "core" / "brain" / "runtime.py").is_file())
            self.assertEqual(
                (agent_root / "core" / "requirements.txt").read_text(encoding="utf-8"),
                "-r brain/requirements.txt\n",
            )
            self.assertTrue((agent_root / "core" / "brain_explorer" / "dist" / "index.html").is_file())
            self.assertFalse((agent_root / "core" / "configs" / "personal.json").exists())
            self.assertFalse((agent_root / "core" / "database" / "live.db").exists())
            self.assertTrue(
                (agent_root / "core" / "assets" / "avatar" / "avatar_working.gif").is_file(),
            )
            self.assertEqual(
                (agent_root / "core" / "assets" / "avatar" / "README.md").read_text(
                    encoding="utf-8",
                ),
                "state contract\n",
            )
            self.assertFalse(
                (agent_root / "core" / "assets" / "avatar" / "personal_portrait.png").exists(),
            )
            self.assertFalse((agent_root / "core" / "brain" / "documentation" / "wiki").exists())

            config = json.loads((agent_root / "core" / "configs" / "brain_configs.json").read_text())
            avatar_config = json.loads(
                (agent_root / "core" / "configs" / "brain_avatar_config.json").read_text(),
            )
            mirrors = json.loads((agent_root / "core" / "configs" / "brain_mirrors.json").read_text())
            self.assertEqual(Path(config["agent_dir"]), agent_root.resolve())
            self.assertEqual(mirrors, [{"name": "@Nova_1", "path": agent_root.as_posix()}])
            self.assertEqual(avatar_config["service"]["host"], "127.0.0.1")
            self.assertGreaterEqual(avatar_config["service"]["port"], 18000)
            self.assertLess(avatar_config["service"]["port"], 38000)

            prompt = (agent_root / "AGENT.md").read_text(encoding="utf-8")
            self.assertIn("@Nova_1", prompt)
            self.assertIn("Alex", prompt)
            self.assertNotIn("@Angi", prompt)
            self.assertNotIn("Yoi", prompt)
            self.assertNotIn("{{", prompt)
            for required_methodology in (
                "Environment Initialization",
                "Response Workflow",
                "Task Execution Workflow",
                "Task planning methodology",
                "Task Execution Guidelines",
                "Exception handling",
                "Declare Results",
            ):
                self.assertIn(required_methodology, prompt)

            launcher = (agent_root / "$agent" / "scripts" / "brain.py").read_text()
            self.assertIn('CORE_ROOT = (HOME_ROOT / Path("../../core")).resolve()', launcher)

            for special_domain in (
                "memory/profiles",
                "memory/diary",
                "$user",
                ".tmp",
            ):
                contents = list((agent_root / special_domain).iterdir())
                self.assertEqual([path.name for path in contents], [".gitkeep"])

            for store_name in ("avatar_storage", "knowledge", "logs", "sources", "vectorstores"):
                store_files = list((agent_root / "core" / "database" / store_name).iterdir())
                self.assertEqual([path.name for path in store_files], [".gitignore"])

    def test_existing_destination_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_core = _fake_core(root)
            parent = root / "agents"
            destination = parent / "@Nova"
            destination.mkdir(parents=True)
            marker = destination / "keep.txt"
            marker.write_text("mine", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                create_agent_directory(
                    parent,
                    "Nova",
                    "Alex",
                    source_core=source_core,
                    instruction_template=UTILITY_ROOT / "AGENT.md",
                )

            self.assertEqual(marker.read_text(encoding="utf-8"), "mine")

    def test_cli_accepts_normalized_and_compatibility_flags(self) -> None:
        args = parse_cli_args(["D:/Agents", "--agent_name", "@Nova", "--user_name", "Alex"])
        self.assertEqual(args.command, "create-agent")
        self.assertEqual(normalize_agent_name(args.agent_name), "Nova")
        self.assertEqual(args.user_name, "Alex")

        update_args = parse_cli_args(["update-agent", "D:/Agents/@Nova", "--json"])
        self.assertEqual(update_args.command, "update-agent")
        self.assertEqual(update_args.path, "D:/Agents/@Nova")

    def test_update_agent_mirrors_only_changed_code_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_core = _fake_core(root)
            result = create_agent_directory(
                root / "agents",
                "Nova",
                "Alex",
                source_core=source_core,
                instruction_template=UTILITY_ROOT / "AGENT.md",
            )
            agent_root = Path(result.agent_root)
            target_core = agent_root / "core"

            (source_core / "brain" / "runtime.py").write_text(
                "RUNTIME = 'updated'\n",
                encoding="utf-8",
            )
            (source_core / "brain" / "new_module.py").write_text("NEW = True\n", encoding="utf-8")
            (target_core / "brain" / "stale.py").write_text("STALE = True\n", encoding="utf-8")
            (target_core / "brain_explorer" / "stale.js").write_text("stale", encoding="utf-8")
            (target_core / "brain" / "node_modules").mkdir()
            (target_core / "brain" / "node_modules" / "local.js").write_text(
                "preserve",
                encoding="utf-8",
            )
            config_marker = target_core / "configs" / "preserve.json"
            database_marker = target_core / "database" / "preserve.db"
            config_marker.write_text("{}", encoding="utf-8")
            database_marker.write_bytes(b"private")

            update = update_agent(agent_root, source_core=source_core)

            self.assertEqual(update.updated_roots, ["brain", "brain_explorer"])
            self.assertEqual(update.copied_files, 2)
            self.assertEqual(update.removed_files, 2)
            self.assertGreaterEqual(update.unchanged_files, 1)
            self.assertEqual(
                (target_core / "brain" / "runtime.py").read_text(encoding="utf-8"),
                "RUNTIME = 'updated'\n",
            )
            self.assertTrue((target_core / "brain" / "new_module.py").is_file())
            self.assertFalse((target_core / "brain" / "stale.py").exists())
            self.assertFalse((target_core / "brain_explorer" / "stale.js").exists())
            self.assertTrue((target_core / "brain" / "node_modules" / "local.js").is_file())
            self.assertEqual(config_marker.read_text(encoding="utf-8"), "{}")
            self.assertEqual(database_marker.read_bytes(), b"private")

            repeated = update_agent(target_core, source_core=source_core)
            self.assertEqual(repeated.copied_files, 0)
            self.assertEqual(repeated.removed_files, 0)
            self.assertEqual(
                repeated.unchanged_files,
                update.unchanged_files + update.copied_files,
            )

    def test_update_agent_refuses_to_update_its_source_core(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source_core = _fake_core(Path(directory))
            with self.assertRaisesRegex(ValueError, "onto itself"):
                update_agent(source_core, source_core=source_core)


if __name__ == "__main__":
    unittest.main()
