#!/usr/bin/env python
"""Relocatable Brain core entrypoint and consumer launcher template."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Directory containing this entrypoint (`core/` or a consumer `$agent/scripts/`).
HOME_ROOT = Path(__file__).resolve().parent

# The factory lives directly under `core`; generated consumers receive a
# relative expression for this line so no machine-specific absolute path is
# embedded in their launchers.
IS_CORE_FACTORY = Path(__file__).name == "core_cli.py" and HOME_ROOT.name == "core"
CORE_ROOT = (HOME_ROOT / Path("../../core")).resolve()

# A consumer launcher always lives at `<workspace>/$agent/scripts/brain.py`.
WORKSPACE_ROOT = CORE_ROOT.parent if IS_CORE_FACTORY else HOME_ROOT.parents[1]

# The consumer contributes only workspace context. `CORE_ROOT` is a bootstrap
# variable used below to import `core/brain/src`; Brain discovers its own core
# container from the installed package and reads agent_dir from core config.
os.environ["WORKSPACE_ROOT"] = str(WORKSPACE_ROOT)


def _prioritize_import_path(path: Path) -> None:
    """Move one resolved import root to the front of `sys.path`."""
    resolved = str(path.resolve())
    normalized = os.path.normcase(os.path.normpath(resolved))
    sys.path[:] = [
        item
        for item in sys.path
        if os.path.normcase(os.path.normpath(os.path.abspath(item or "."))) != normalized
    ]
    sys.path.insert(0, resolved)


def main() -> int:
    """Run the brain command-line interface from the repository root."""
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass

    # Allow create-brain to run from template/factory file
    is_init_cmd = len(sys.argv) > 1 and sys.argv[1] == "create-brain"

    if IS_CORE_FACTORY and not is_init_cmd:
        print("Error: core_cli.py is the consumer factory, not a workspace Brain facade.", file=sys.stderr)
        print("\nStep 1: Ensure you initialize your target workspace root:", file=sys.stderr)
        print("        python core/core_cli.py create-brain <target_workspace_root>", file=sys.stderr)
        print("\nStep 2: Run commands using your local workspace facade copy:", file=sys.stderr)
        print("        python $agent/scripts/brain.py <command>", file=sys.stderr)
        return 1

    brain_src_dir = CORE_ROOT / "brain" / "src"
    for import_root in (HOME_ROOT, CORE_ROOT, brain_src_dir):
        _prioritize_import_path(import_root)

    if len(sys.argv) > 1 and sys.argv[1] == "speak":
        from brain.infrastructure.voice.service import VoiceService

        arguments = sys.argv[2:]
        language = "es"
        emotion = ""
        codex_thread_id = ""
        text = ""
        index = 0
        while index < len(arguments):
            argument = arguments[index]
            if argument in {"-l", "--lang"} and index + 1 < len(arguments):
                language = arguments[index + 1]
                index += 2
                continue
            if argument in {"-tx", "--text"} and index + 1 < len(arguments):
                text = arguments[index + 1]
                index += 2
                continue
            if argument == "--emotion" and index + 1 < len(arguments):
                emotion = arguments[index + 1]
                index += 2
                continue
            if argument == "--codex-thread-id" and index + 1 < len(arguments):
                codex_thread_id = arguments[index + 1]
                index += 2
                continue
            if not argument.startswith("-") and not text:
                text = argument
            index += 1
        VoiceService().speak(
            text=text,
            lang=language,
            emotion=emotion,
            codex_thread_id=codex_thread_id,
        )
        return 0

    from brain.cli import main as brain_main
    return brain_main()


if __name__ == "__main__":
    raise SystemExit(main())
