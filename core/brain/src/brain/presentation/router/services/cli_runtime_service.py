"""Runtime service that coordinates Brain CLI parsing, dispatch, and error rendering."""

from __future__ import annotations

import json
import sys

from brain.application.memory.paths import BrainStoreError
from brain.presentation.commands.registry import COMMAND_MODULES
from brain.presentation.parser.services.argument_parser_service import build_argument_parser
from brain.presentation.parser.services.global_flags_service import extract_global_flags
from brain.presentation.router.services.command_router_service import dispatch_command
from brain.presentation.terminal import ANSI_RED, ANSI_RESET


def run_cli(argv: list[str] | None = None) -> int:
    """Parse CLI arguments, execute the selected action, and return a process code."""
    raw_argv: list[str] = sys.argv[1:] if argv is None else argv
    parsed_argv, color_enabled, verbose_log = extract_global_flags(argv=raw_argv)
    parser = build_argument_parser(command_modules=COMMAND_MODULES)
    args = parser.parse_args(parsed_argv)
    args.color = color_enabled
    args.verbose_log = verbose_log

    try:
        return dispatch_command(args=args)
    except BrainStoreError as exc:
        if getattr(args, "json", False):
            payload = {
                "ok": False,
                "command": getattr(args, "command", None),
                "error": str(exc),
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 1
        if color_enabled:
            print(f"{ANSI_RED}Error: {exc}{ANSI_RESET}", file=sys.stderr)
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1
