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

from brain.presentation.json_renderer import render_json
from brain.presentation.terminal import (
    ANSI_BOLD,
    ANSI_CYAN,
    ANSI_DIM,
    ANSI_GREEN,
    ANSI_MAGENTA,
    ANSI_YELLOW,
    log_step,
)


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


class JsonRendererTests(unittest.TestCase):
    """Validate compact and semantic-color JSON presentation modes."""

    def test_standard_json_is_compact_and_parseable(self) -> None:
        """Machine JSON must not contain indentation or separator whitespace."""
        rendered = render_json({"text": "Angi", "count": 2, "ready": True, "missing": None})

        self.assertEqual(rendered, '{"text":"Angi","count":2,"ready":true,"missing":null}')

    def test_colored_json_is_indented_and_uses_semantic_schema(self) -> None:
        """Colored JSON assigns stable ANSI colors to every primitive token class."""
        rendered = render_json(
            {"text": "Angi", "count": 2, "ready": True, "missing": None},
            color_enabled=True,
        )

        self.assertIn("\n  ", rendered)
        self.assertIn(f'{ANSI_BOLD}{ANSI_CYAN}"text"', rendered)
        self.assertIn(f'{ANSI_GREEN}"Angi"', rendered)
        self.assertIn(f"{ANSI_YELLOW}2", rendered)
        self.assertIn(f"{ANSI_MAGENTA}true", rendered)
        self.assertIn(f"{ANSI_DIM}null", rendered)


if __name__ == "__main__":
    unittest.main()
