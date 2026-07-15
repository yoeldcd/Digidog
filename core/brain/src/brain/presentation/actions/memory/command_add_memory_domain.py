"""Action module to create a memory domain."""

from __future__ import annotations

import argparse
import json

from brain.application.memory.service import create_category
from brain.presentation.terminal import render_placeholders, log_step



def handle(args: argparse.Namespace) -> int:
    """Create memory domain."""
    color_enabled = getattr(args, "color", False)
    log_step(args, "[1/2] Validating domain inputs...")
    try:
        domain_name = args.domain.strip()
        log_step(args, f"[2/2] Creating memory domain '{domain_name}'...")
        domain_path = create_category(domain_name)
        if args.json:
            print(
                json.dumps(
                    {"ok": True, "domain": domain_name, "path": domain_path.as_posix()},
                    ensure_ascii=False,
                    indent=2,
                ),
                flush=True,
            )
            return 0
        msg = f"__GREEN__Created memory domain__RESET__ '__CYAN__{domain_name}__RESET__'."
        print(render_placeholders(msg, color_enabled), flush=True)
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), flush=True)
            return 1
        msg = f"__RED__Error: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled), flush=True)
        return 1
