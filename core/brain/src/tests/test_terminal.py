# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Tests for terminal progress logging behavior."""

from __future__ import annotations

import argparse
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from brain.presentation.terminal import log_step


class TerminalVerboseLogTests(unittest.TestCase):
    """Validate the CLI progress-output contract."""

    def test_log_step_is_quiet_without_verbose_log(self) -> None:
        args = argparse.Namespace(color=False, verbose_log=False)

        with redirect_stdout(io.StringIO()) as stdout:
            log_step(args, "[1/2] Hidden progress")

        self.assertEqual(stdout.getvalue(), "")

    def test_log_step_prints_with_verbose_log(self) -> None:
        args = argparse.Namespace(color=False, verbose_log=True)

        with redirect_stdout(io.StringIO()) as stdout:
            log_step(args, "[1/2] Visible progress")

        self.assertIn("[1/2] Visible progress", stdout.getvalue())

    def test_log_step_prints_task_prefix_for_numbered_steps(self) -> None:
        args = argparse.Namespace(color=False, verbose_log=True)

        with redirect_stdout(io.StringIO()) as stdout:
            log_step(args, "[3/7] Updating memory index...", task="initialization")

        self.assertIn("initialization steep [3/7] Updating memory index...", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
