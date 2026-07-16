# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to perform semantic vector search on local workspace logs."""

from __future__ import annotations

import argparse
import json
from brain.infrastructure.runtime.paths import get_vectorstore_dir, get_workspace_root
from brain.infrastructure.vectorstores.manager import VectorStoreManager
from brain.presentation.terminal import render_placeholders, render_markdown, log_step




def handle(args: argparse.Namespace) -> int:
    """Execute semantic query on workspace logs."""
    log_step(args, 'Querying local logs database...')
    color_enabled = getattr(args, "color", False)
    try:
        domain = args.domain
        query_val = args.query

        # Handle arguments positional shift
        if domain is not None and query_val is None:
            query_str = domain
            domain = None
        elif domain is not None and query_val is not None:
            query_str = query_val
        else:
            msg = "__RED__Error: Semantic query string is required.__RESET__"
            print(render_placeholders(msg, color_enabled))
            return 1


        workspace_root = get_workspace_root()
        db_path = get_vectorstore_dir(scope="local", workspace_root=workspace_root)
        manager = VectorStoreManager(db_path=db_path, collection_name="logs")
        if manager.count_records() == 0:
            from brain.application.logs.index_service import migrate_legacy_log_files_to_database, migrate_log_files_to_database
            from brain.application.logs.store import list_log_entries, log_database_summary

            entry_count, _domain_count, _latest_count = log_database_summary(workspace_root=workspace_root)
            if entry_count == 0:
                migrate_legacy_log_files_to_database(workspace_root=workspace_root, archive_sources=False)
                migrate_log_files_to_database(workspace_root=workspace_root, archive_sources=False)
            log_entries = list_log_entries(workspace_root=workspace_root)
            if log_entries:
                manager.index_log_entries(log_entries)
        if domain:
            from brain.application.logs.query_service import resolve_query_log_domain
            from brain.application.logs.store import list_log_domains

            domain = resolve_query_log_domain(domain, list_log_domains(workspace_root=workspace_root))
        matches = manager.search_logs(query_str, domain_filter=domain, limit=args.limit)
        args.narration_query = query_str
        args.narration_result_count = len(matches)

        if args.json:
            print(json.dumps(matches, ensure_ascii=False, indent=2))
        else:
            if not matches:
                msg = "__YELLOW__No matching log entries found.__RESET__"
                print(render_placeholders(msg, color_enabled))
                return 0

            print(render_placeholders(f"# Log Semantic Matches for: '__CYAN__{query_str}__RESET__'", color_enabled))
            print()
            for m in matches:
                score_str = f"__GREEN__({m['similarity']:.2%} similarity)__RESET__"
                recency_str = f"__DIM__(Recency: {m['recency_factor']:.2f})__RESET__"
                path_str = f"__CYAN__{m['domain']}__RESET__ [ {m['title']} ]"
                read_command = m.get("read_command") or ""
                read_text = f" readed `{read_command}`" if read_command else ""
                print(
                    render_placeholders(
                        f"- {path_str}{read_text} - {score_str} {recency_str} at "
                        f"__YELLOW__{m['timestamp']}__RESET__:",
                        color_enabled,
                    ),
                )
                print(render_markdown("```md", color_enabled))
                print(m["text"])
                print(render_markdown("```", color_enabled))
                print()

        return 0
    except Exception as exc:
        msg = f"__RED__Error during query-log: {exc}__RESET__"
        print(render_placeholders(msg, color_enabled))
        return 1
