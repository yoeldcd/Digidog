# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to perform semantic vector search on local workspace logs."""

from __future__ import annotations

import argparse
import json
from brain.infrastructure.runtime.paths import get_vectorstore_dir, get_workspace_root
from brain.infrastructure.vectorstores.manager import VectorStoreManager
from brain.presentation.terminal import render_placeholders, render_markdown, log_step

def _live_policy_matches() -> list[dict[str, object]]:
    """Project every local policy record into every log-query response."""
    from brain.application.records.service import list_live_records

    return [
        {"domain": "policies", "title": record.id, "text": record.text, "similarity": 1.0, "recency_factor": 1.0,
         "timestamp": record.created_at, "read_command": "show-policies --json", "mechanism": "live_context"}
        for record in list_live_records()
    ]




def handle(args: argparse.Namespace) -> int:
    """Run a semantic search against workspace log entries.

    Args:
        args (argparse.Namespace): Parsed command options with the query, optional
            domain restriction, result limit, and output format.

    Returns:
        int: Zero when the search completes; otherwise one after reporting an
            error.
    """
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
        if domain:
            from brain.application.logs.query_service import resolve_query_log_domain
            from brain.application.logs.store import list_log_domains

            domain = resolve_query_log_domain(domain, list_log_domains(workspace_root=workspace_root))
        try:
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
            matches = manager.search_logs(query_str, domain_filter=domain, limit=args.limit)
            for match in matches:
                match.setdefault("mechanism", "vector")
        except Exception as search_error:
            from brain.application.logs.query_service import search_log_text_matches
            from brain.infrastructure.vectorstores.recovery import is_embedding_unavailable_error

            if not is_embedding_unavailable_error(search_error) and "embedding" not in str(search_error).casefold():
                raise
            matches = search_log_text_matches(
                workspace_root=workspace_root,
                query=query_str,
                domain_filter=domain,
                limit=args.limit,
                fallback_reason=str(search_error),
            )
            args.embedding_unavailable = str(search_error)
        args.narration_query = query_str
        log_matches = matches
        policies = _live_policy_matches()
        matches = policies + log_matches
        args.narration_result_count = len(log_matches)
        args.narration_output = ''
        args.narration_table_columns = ['source', 'domain', 'content|entity']
        args.narration_table_rows = [
            {'source': 'records' if match.get('domain') == 'policies' else 'logs',
             'domain': match.get('domain', ''),
             'content|entity': match.get('text') or match.get('title', '')}
            for match in matches
        ]

        if args.json:
            print(json.dumps({'ok': True, 'command': 'query-log', 'query': query_str, 'domain': domain, 'limit': args.limit, 'counts': {'policies': len(policies), 'matches': len(log_matches)}, 'policies': policies, 'matches': log_matches}, ensure_ascii=False, indent=2))
        else:
            if not policies and not log_matches:
                msg = "__YELLOW__No matching log entries found.__RESET__"
                print(render_placeholders(msg, color_enabled))
                return 0

            print(render_placeholders(f"# Workspace log query: '__CYAN__{query_str}__RESET__'", color_enabled))
            if policies:
                print(render_placeholders("## __GREEN__Active workspace policies__RESET__", color_enabled))
            if not log_matches:
                print(render_placeholders("__YELLOW__No matching log entries found.__RESET__", color_enabled))
            elif not policies:
                print(render_placeholders("## __GREEN__Matching log entries__RESET__", color_enabled))
            print()
            for index, m in enumerate(matches):
                if policies and index == len(policies):
                    print(render_placeholders("## __GREEN__Matching log entries__RESET__", color_enabled))
                score_str = f"__GREEN__({m['similarity']:.2%} similarity)__RESET__"
                recency_str = f"__DIM__(Recency: {m['recency_factor']:.2f})__RESET__"
                path_str = f"__CYAN__{m['domain']}__RESET__ [ {m['title']} ]"
                read_command = m.get("read_command") or ""
                read_text = f"; read with `{read_command}`" if read_command else ""
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
