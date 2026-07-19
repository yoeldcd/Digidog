"""Regression tests for model secret resolution in long-lived Windows services."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from brain.application.knowledge.runtime import config_store
from brain.infrastructure.vectorstores import settings


class SecretResolutionTests(unittest.TestCase):
    """Keep inherited values authoritative while supporting persisted fallbacks."""

    def test_inherited_environment_value_wins(self) -> None:
        with (
            patch.dict(config_store.os.environ, {"MODEL_KEY": "inherited-key"}, clear=True),
            patch.object(config_store, "_resolve_windows_environment_secret") as persisted,
        ):
            self.assertEqual(config_store.resolve_secret("$MODEL_KEY"), "inherited-key")
        persisted.assert_not_called()

    def test_persisted_environment_value_fills_stale_process_state(self) -> None:
        with (
            patch.dict(config_store.os.environ, {}, clear=True),
            patch.object(config_store, "_resolve_windows_environment_secret", return_value="persisted-key"),
        ):
            self.assertEqual(config_store.resolve_secret("$MODEL_KEY"), "persisted-key")

    def test_unresolved_reference_remains_explicit(self) -> None:
        with (
            patch.dict(config_store.os.environ, {}, clear=True),
            patch.object(config_store, "_resolve_windows_environment_secret", return_value=""),
        ):
            self.assertEqual(config_store.resolve_secret("$MODEL_KEY"), "$MODEL_KEY")

    def test_vectorstore_config_uses_shared_secret_resolver(self) -> None:
        with patch.object(settings, "resolve_secret", return_value="shared-key") as resolver:
            self.assertEqual(settings._resolve_config_value("$OPENROUTER_API_KEY"), "shared-key")
        resolver.assert_called_once_with("$OPENROUTER_API_KEY")


if __name__ == "__main__":
    unittest.main()
