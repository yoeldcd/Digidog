"""Action module to write pure Markdown content to a category/key."""

from __future__ import annotations

import argparse
import json
from brain.application.memory.service import write_instance
from brain.presentation.terminal import render_placeholders, log_step



def handle(args: argparse.Namespace) -> int:
    """Save memory domain instance content."""
    color_enabled = getattr(args, "color", False)
    try:
        log_step(args, '[1/2] Resolving domain...')
        import sys
        domain = args.domain
        key = args.key
        val = args.val

        # Determine key and value based on dot notation
        if "." in domain:
            value = key
            domain, key = domain.rsplit(".", 1)
        else:
            value = val

        # Allow --value option to override if provided explicitly
        if getattr(args, "value", None) is not None:
            value = args.value

        if key is None:
            err_msg = "key must be specified either as a second argument or using dot notation (domain.key)."
            if args.json:
                print(json.dumps({"ok": False, "error": err_msg}, ensure_ascii=False))
            else:
                msg = f"__RED__Error: {err_msg}__RESET__"
                print(render_placeholders(msg, color_enabled))
            return 1

        if value is None or value == "-":
            value = sys.stdin.read()

        log_step(args, '[2/2] Writing entry...')
        file_path = write_instance(domain, key, value)
        if args.json:
            result = {
                "ok": True,
                "domain": domain,
                "key": key,
                "path": file_path.as_posix()
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            msg = f"__GREEN__Saved key__RESET__ '__GREEN__{key}__RESET__' in domain '__CYAN__{domain}__RESET__'."
            print(render_placeholders(msg, color_enabled))
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            msg = f"__RED__Error: {exc}__RESET__"
            print(render_placeholders(msg, color_enabled))
        return 1
