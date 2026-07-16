# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to query the private knowledge graph."""

from __future__ import annotations

# Standard Libraries Imports
import argparse
import json

# Application Modules Imports
from brain.application.knowledge.runtime.scopes import iter_knowledge_roots
from brain.application.knowledge.querying.query import query_knowledge
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.application.knowledge.sources.freshness import check_source_updates
from brain.presentation.terminal import render_markdown, render_placeholders, log_step




def handle(args: argparse.Namespace) -> int:
    """Search knowledge graph records."""
    color_enabled: bool = getattr(args, "color", False)
    try:
        log_step(args, "Querying knowledge graph...")
        results: list[dict] = []
        for scope_name, knowledge_root in iter_knowledge_roots(scope=str(args.scope)):
            repository = KnowledgeRepository(knowledge_root=knowledge_root, scope=scope_name)
            update_check: dict = check_source_updates(repository=repository, source_scope=scope_name)
            if int(update_check.get("changed") or 0) or int(update_check.get("deleted") or 0):
                results.append(
                    {
                        "kind": "warning",
                        "rank": 998.0,
                        "scope": scope_name,
                        "data": {
                            "warning": (
                                f"{update_check.get('changed', 0)} changed and "
                                f"{update_check.get('deleted', 0)} deleted sources need a dream pass."
                            ),
                            "knowledge_scope": scope_name,
                        },
                    },
                )
            scope_results: list[dict] = query_knowledge(
                repository=repository,
                text=args.query,
                limit=args.limit,
                hybrid=args.hybrid,
            )
            for result in scope_results:
                result["scope"] = scope_name
                result.setdefault("data", {})["knowledge_scope"] = scope_name
            results.extend(scope_results)
        results.sort(key=lambda item: (float(item.get("rank", 0.0)), str(item.get("scope", ""))))
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
            return 0

        if not results:
            print(render_placeholders("__YELLOW__No knowledge matches found.__RESET__", color_enabled))
            return 0

        print(render_placeholders(f"# Knowledge Matches for: __CYAN__{args.query}__RESET__", color_enabled))
        for result in results:
            data: dict = result.get("data", {})
            title: str = str(
                data.get("canonical_name")
                or data.get("quote")
                or data.get("title")
                or data.get("warning")
                or data.get("id"),
            )
            if result.get("kind") == "warning":
                print(render_placeholders(f"- __YELLOW__Warning [{result.get('scope', '')}]__RESET__: {title}", color_enabled))
                continue
            if args.explain:
                detail_line: str = (
                    f"- __GREEN__{result['kind']}[{result.get('scope', '')}]__RESET__ "
                    f"rank={result['rank']}: {title}"
                )
                print(render_placeholders(detail_line, color_enabled))
            else:
                print(render_markdown(f"- **{result['kind']} [{result.get('scope', '')}]**: {title}", color_enabled))
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(render_placeholders(f"__RED__Error: {exc}__RESET__", color_enabled))
        return 1
