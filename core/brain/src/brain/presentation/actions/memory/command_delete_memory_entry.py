"""Action module to delete a memory domain or a specific memory entry."""

from __future__ import annotations

import argparse
import json

from brain.application.memory.service import delete_category, delete_instance
from brain.presentation.terminal import render_placeholders, log_step


def handle(args: argparse.Namespace) -> int:
    """Execute deletion of key or memory domain."""
    color_enabled = getattr(args, "color", False)
    log_step(args, "[1/2] Resolving target...")
    try:
        domain = args.domain
        key = args.key
        if key is None and "." in domain:
            from brain.application.memory.paths import resolve_category_dir
            try:
                cat_dir = resolve_category_dir(domain)
                if not cat_dir.is_dir():
                    domain, key = domain.rsplit(".", 1)
            except Exception:
                domain, key = domain.rsplit(".", 1)

        if key:
            log_step(args, f"[2/2] Deleting key '{key}'...")
            delete_instance(domain, key)
            if args.json:
                result = {"ok": True, "domain": domain, "key": key, "deleted": "entry"}
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0
            msg = (
                f"__GREEN__Deleted key__RESET__ '__GREEN__{key}__RESET__' "
                f"from memory domain '__CYAN__{domain}__RESET__'."
            )
            print(render_placeholders(msg, color_enabled))
        else:
            if not args.confirm:
                error = f"Deleting the entire memory domain '{domain}' requires --confirm {domain}."
                if args.json:
                    print(json.dumps({"ok": False, "error": error}, ensure_ascii=False))
                    return 1
                msg = f"__RED__Error: {error}__RESET__"
                print(render_placeholders(msg, color_enabled))
                return 1
            log_step(args, f"[2/2] Deleting entire memory domain '{domain}'...")
            delete_category(domain, args.confirm)
            if args.json:
                result = {"ok": True, "domain": domain, "deleted": "domain"}
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0
            msg = f"__GREEN__Deleted memory domain__RESET__ '__CYAN__{domain}__RESET__'."
            print(render_placeholders(msg, color_enabled))
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            return 1
        msg = f"__RED__Error: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled))
        return 1
