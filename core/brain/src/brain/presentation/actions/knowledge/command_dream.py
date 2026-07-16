# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to run cognitive knowledge graph consolidation."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
import json
from typing import Any

# Application Modules Imports
from brain.presentation.actions.knowledge.dream_flow import run_dream_scope
from brain.presentation.actions.knowledge.dream_scope_plan import resolve_dream_scope_plan
from brain.presentation.terminal import log_step, render_placeholders


def handle(args: argparse.Namespace) -> int:
    """Run the dream consolidation pipeline."""
    color_enabled: bool = getattr(args, "color", False)
    try:
        scope_plan: list[dict[str, str]] = resolve_dream_scope_plan(
            scope=str(args.scope),
            domain=str(args.domain),
        )
        if not bool(args.json):
            log_step(args, "Running cognitive dream proposal pass...")
        result_payloads: list[dict[str, Any]] = []
        exit_code: int = 0
        for scope_item in scope_plan:
            scope_exit_code, scope_payload = run_dream_scope(
                args=args,
                scope_name=scope_item["scope"],
                source_domain=scope_item["domain"],
                color_enabled=color_enabled,
            )
            result_payloads.append(scope_payload)
            if scope_exit_code != 0:
                exit_code = scope_exit_code
                break
        if args.json:
            print(
                json.dumps(
                    result_payloads[0]
                    if len(result_payloads) == 1
                    else {"ok": exit_code == 0, "scope_results": result_payloads},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        return exit_code
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(render_placeholders(f"__RED__Error: {exc}__RESET__", color_enabled))
        return 1
