"""Action module to refresh the memory source registry."""

from __future__ import annotations

import argparse
import json
from brain.presentation.terminal import render_placeholders, log_step



def handle(args: argparse.Namespace) -> int:
    """Refresh memory source registry."""
    color_enabled = getattr(args, "color", False)
    log_step(args, 'Rebuilding memory index...')
    try:
        from brain.application.memory import paths
        from brain.application.sources.registry_service import refresh_source_registry
        from brain.domain.sources.classification import memory_source_type

        paths.ensure_memory_root()
        refresh_source_registry(
            scope="global",
            root=paths.MEMORY_ROOT,
            root_prefix="memory",
            suffixes=(".md",),
            source_type_resolver=memory_source_type,
        )

        if args.json:
            print(json.dumps({"ok": True, "message": "Memory source registry refreshed."}, ensure_ascii=False))
        else:
            msg = "__GREEN__Memory source registry has been refreshed from filesystem mtimes.__RESET__"
            print(render_placeholders(msg, color_enabled))
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            msg = f"__RED__Error: {exc}__RESET__"
            print(render_placeholders(msg, color_enabled))
        return 1
