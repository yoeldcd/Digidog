"""Action module to completely index or rebuild local collections in ChromaDB."""

from __future__ import annotations

import argparse
import json
from brain.infrastructure.runtime.paths import get_vectorstore_dir, get_workspace_root
from brain.infrastructure.vectorstores.manager import VectorStoreManager
from brain.presentation.terminal import render_placeholders, log_step




def handle(args: argparse.Namespace) -> int:
    """Rebuild local vector collection."""
    collection = args.collection.strip().lower()
    color_enabled = getattr(args, "color", False)

    # Prompt for confirmation unless --yes is supplied
    if not getattr(args, "yes", False):
        try:
            print(f"⚠️ WARNING: This is a DESTRUCTIVE command that resets and rebuilds the local vectorstore collection '{collection}' from scratch.")
            print("For incremental updates, please use 'update-local-vectorstore'.")
            confirm = input("Are you sure you want to proceed? (y/N): ").strip().lower()
            if confirm not in ("y", "yes"):
                print("Aborted.")
                return 0
        except Exception:
            print("Aborted: Confirmation required. Run with --yes flag in non-interactive environments.")
            return 1

    log_step(args, f"Rebuilding local vectorstore collection '{collection}'...")
    try:
        workspace_root = get_workspace_root()
        db_path = get_vectorstore_dir(scope="local", workspace_root=workspace_root)

        manager = VectorStoreManager(db_path=db_path, collection_name=collection)
        entries_deleted = manager.count_records()
        manager.reset_store()  # reset the collection

        if collection == "logs":
            from brain.application.logs.index_service import migrate_legacy_log_files_to_database, migrate_log_files_to_database
            from brain.application.logs.store import list_log_entries, log_database_summary

            entry_count, _domain_count, _latest_count = log_database_summary(workspace_root=workspace_root)
            if entry_count == 0:
                migrate_legacy_log_files_to_database(workspace_root=workspace_root, archive_sources=False)
                migrate_log_files_to_database(workspace_root=workspace_root, archive_sources=False)

            log_entries = list_log_entries(workspace_root=workspace_root)
            if not log_entries:
                msg = "__YELLOW__No DB-backed log entries found to index.__RESET__"
                if args.json:
                    print(json.dumps({"ok": True, "count": 0, "message": msg}, ensure_ascii=False))
                else:
                    print(render_placeholders(msg, color_enabled))
                return 0

            stats = manager.index_log_entries(log_entries)
            indexed_count = 1
            entries_created = int(stats.get("entries_created") or 0)
            file_stats = [stats]
            if not args.json and getattr(args, "verbose_log", False):
                print(
                    render_placeholders(
                        "  vectorized __CYAN__{path}__RESET__: entries __GREEN__{entries}__RESET__".format(
                            path=stats.get("path") or "database/brain_logs.db",
                            entries=entries_created,
                        ),
                        color_enabled,
                    ),
                )

            if args.json:
                print(
                    json.dumps(
                        {
                            "ok": True,
                            "indexed_files": indexed_count,
                            "entries_created": entries_created,
                            "entries_deleted": entries_deleted,
                            "files": file_stats,
                            "message": f"Successfully indexed {entries_created} DB log entries.",
                        },
                        ensure_ascii=False,
                    ),
                )
            else:
                msg = (
                    f"__GREEN__Successfully rebuilt local collection '{collection}'__RESET__: "
                    f"indexed __CYAN__{entries_created}__RESET__ DB log entries; "
                    f"entries created __GREEN__{entries_created}__RESET__, entries deleted __YELLOW__{entries_deleted}__RESET__."
                )
                print(render_placeholders(msg, color_enabled))
        else:
            raise ValueError(f"Collection '{collection}' is not recognized for rebuilding.")

        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            msg = f"__RED__Error: {exc}__RESET__"
            print(render_placeholders(msg, color_enabled))
        return 1
