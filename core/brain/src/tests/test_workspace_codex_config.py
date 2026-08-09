# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Regression tests for restrictive WoSP-local Codex configuration."""

from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

from brain.application.workspace.bootstrap_service import ensure_workspace_codex_config, ensure_workspace_codex_rules


class WorkspaceCodexConfigTests(unittest.TestCase):
    """Validate safe creation and preservation of project-local Codex policy."""

    def test_create_config_selects_agent_guard_with_auto_review(self) -> None:
        """Create a parsable selected local guard whose escalations use Auto Review."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)

            created = ensure_workspace_codex_config(
                workspace=workspace,
                agent_name="@Example",
                agent_dir=Path("D:/agents/@Example"),
            )

            config_file = workspace / ".codex" / "config.toml"
            config = tomllib.loads(config_file.read_text(encoding="utf-8"))
            self.assertTrue(created)
            self.assertEqual(config["approval_policy"], "on-request")
            self.assertEqual(config["approvals_reviewer"], "auto_review")
            self.assertEqual(config["default_permissions"], "example_workspace_guard")
            self.assertFalse(config["allow_login_shell"])
            guard = config["permissions"]["example_workspace_guard"]
            self.assertEqual(guard["extends"], ":read-only")
            self.assertEqual(guard["filesystem"]["D:/agents/@Example"], "write")
            self.assertEqual(guard["filesystem"][":workspace_roots"]["."], "write")
            self.assertEqual(guard["filesystem"][":workspace_roots"]["**/.env"], "deny")
            self.assertNotIn("sandbox_mode", config)
            self.assertNotIn("sandbox_workspace_write", config)
            self.assertNotIn("shell_environment_policy", config)

    def test_create_rules_declares_brain_prefix_and_preserves_existing_file(self) -> None:
        """Create the Brain rule beside config.toml without overwriting ownership."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)

            self.assertTrue(ensure_workspace_codex_rules(workspace=workspace))
            rules_file = workspace / ".codex" / "rules" / "default.rules"
            original = rules_file.read_text(encoding="utf-8")
            self.assertIn('pattern = ["py", ".\\\\$agent\\\\scripts\\\\brain.py"]', original)

            rules_file.write_text(original + "\n# project-owned\n", encoding="utf-8")
            self.assertFalse(ensure_workspace_codex_rules(workspace=workspace))
            self.assertTrue(rules_file.read_text(encoding="utf-8").endswith("# project-owned\n"))

    def test_only_create_brain_supervises_codex_artifacts(self) -> None:
        """Keep Codex policy creation out of recurring init and wakeup calls."""
        import inspect
        from brain.presentation.actions.general import command_create_brain, command_init

        create_source = inspect.getsource(command_create_brain.handle)
        init_source = inspect.getsource(command_init.handle)
        self.assertIn("ensure_workspace_codex_config", create_source)
        self.assertIn("ensure_workspace_codex_rules", create_source)
        self.assertNotIn("ensure_workspace_codex_config", init_source)
        self.assertNotIn("ensure_workspace_codex_rules", init_source)
        self.assertNotIn('workspace_root / ".codex"', init_source)

    def test_existing_config_is_preserved(self) -> None:
        """Never overwrite a project-owned Codex configuration."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            config_file = workspace / ".codex" / "config.toml"
            config_file.parent.mkdir(parents=True)
            original = 'approval_policy = "never"\n'
            config_file.write_text(original, encoding="utf-8")

            created = ensure_workspace_codex_config(
                workspace=workspace,
                agent_name="@Example",
                agent_dir=Path("D:/agents/@Example"),
            )

            self.assertFalse(created)
            self.assertEqual(config_file.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
