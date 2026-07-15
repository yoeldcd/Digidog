"""Action module to run store validation checks."""

from __future__ import annotations

import argparse
import json
from typing import Any

from brain.application.memory.diagnostics import doctor_report
from brain.presentation.terminal import render_placeholders, log_step



def print_json(payload: Any) -> None:
    """Print a payload as stable UTF-8 JSON."""
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def handle(args: argparse.Namespace) -> int:
    """Run integrity check on memory directory tree structure."""
    log_step(args, 'Validating workspace memory structure...')
    report = doctor_report()
    if args.json:
        print_json(report)
    else:
        color_enabled = getattr(args, "color", False)
        if report["ok"]:
            msg = "__GREEN__Memory structure OK.__RESET__"
            print(render_placeholders(msg, color_enabled))
        else:
            msg = "__RED__Memory structure has errors.__RESET__"
            print(render_placeholders(msg, color_enabled))
        for warning in report["warnings"]:
            msg = f"__YELLOW__WARNING: {warning}__RESET__"
            print(render_placeholders(msg, color_enabled))
        for error in report["errors"]:
            msg = f"__RED__ERROR: {error}__RESET__"
            print(render_placeholders(msg, color_enabled))
    return 0 if report["ok"] else 1
