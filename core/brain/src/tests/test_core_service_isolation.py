# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Regression tests for independent services across physical agent cores."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from brain.infrastructure.voice.config import resolve_voice_daemon_endpoint
from brain.infrastructure.voice.daemon_client import VoiceDaemonClient
from brain.infrastructure.voice.process_lease import core_process_lease_name, core_runtime_id


class CoreServiceIsolationTests(unittest.TestCase):
    """Keep daemon transport and process leases inside one core boundary."""

    def test_voice_endpoint_is_owned_by_avatar_config(self) -> None:
        self.assertEqual(
            resolve_voice_daemon_endpoint({"service": {"host": "127.0.0.1", "port": 19133}}),
            ("127.0.0.1", 19133),
        )

    def test_daemon_and_window_leases_differ_across_cores(self) -> None:
        first = Path("D:/agents/@First/core")
        second = Path("D:/agents/@Second/core")
        self.assertNotEqual(core_runtime_id(first), core_runtime_id(second))
        self.assertNotEqual(
            core_process_lease_name("voice-daemon", first),
            core_process_lease_name("voice-daemon", second),
        )
        self.assertNotEqual(
            core_process_lease_name("voice-daemon", first),
            core_process_lease_name("voice-avatar-window", first),
        )

    def test_client_rejects_foreign_core_health(self) -> None:
        client = VoiceDaemonClient()
        with patch.object(client, "_request_json", return_value={"ok": True, "coreId": "foreign-core"}):
            self.assertFalse(client._is_healthy())


if __name__ == "__main__":
    unittest.main()
