"""Action module to rebuild the ChromaDB vector store from scratch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from brain.application.knowledge.vector_sync import sync_all_knowledge_vectorstores
from brain.application.memory.paths import MEMORY_ROOT
from brain.infrastructure.vectorstores.manager import VectorStoreManager
from brain.presentation.terminal import render_placeholders, log_step



def handle(args: argparse.Namespace) -> int:
    """Rebuild vectorstore."""
    color_enabled = getattr(args, "color", False)

    # Prompt for confirmation unless --yes is supplied
    if not getattr(args, "yes", False):
        try:
            print("⚠️ WARNING: This is a DESTRUCTIVE command that resets and rebuilds the shared vectorstore from scratch.")
            print("For incremental updates, please use 'update-vectorstore'.")
            confirm = input("Are you sure you want to proceed? (y/N): ").strip().lower()
            if confirm not in ("y", "yes"):
                print("Aborted.")
                return 0
        except Exception:
            print("Aborted: Confirmation required. Run with --yes flag in non-interactive environments.")
            return 1

    log_step(args, '[1/2] Resetting semantic database...')
    try:
        manager = VectorStoreManager()
        entries_deleted = manager.count_records()
        manager.reset_store()

        indexed_count = 0
        entries_created = 0
        file_stats = []
        knowledge_stats = []
        knowledge_warnings = []
        memory_dir = Path(MEMORY_ROOT)

        # Discover all .md files under memory/
        md_files = []
        for p in memory_dir.rglob("*.md"):
            # Skip metadata index files at the root
            if p.parent == memory_dir:
                continue
            md_files.append(p)

        total_files = len(md_files)

        # Index each file
        log_step(args, '[2/2] Indexing all memory files...')
        for p in md_files:
            # Resolve category and key from path
            rel = p.relative_to(memory_dir)
            parts = rel.parts

            if len(parts) >= 2:
                category = ".".join(parts[:-1])
                key = p.stem
            else:
                continue

            content = p.read_text(encoding="utf-8")
            stats = manager.add_or_update_file(category, key, content)
            file_stats.append(stats)
            entries_created += int(stats.get("entries_created") or 0)
            indexed_count += 1
            if not args.json and getattr(args, "verbose_log", False):
                print(
                    render_placeholders(
                        "  vectorized __CYAN__{path}__RESET__: entries __GREEN__{entries}__RESET__".format(
                            path=stats.get("path") or p.as_posix(),
                            entries=stats.get("entries_created") or 0,
                        ),
                        color_enabled,
                    ),
                )

        knowledge_stats, knowledge_warnings = sync_all_knowledge_vectorstores()

        if args.json:
            print(json.dumps({
                "ok": True,
                "message": "Vector store rebuilt successfully.",
                "indexed_files": indexed_count,
                "entries_created": entries_created,
                "entries_deleted": entries_deleted,
                "total_discovered": total_files,
                "files": file_stats,
                "knowledge": knowledge_stats,
                "warnings": knowledge_warnings,
            }, ensure_ascii=False))
        else:
            for warning in knowledge_warnings:
                print(render_placeholders(f"  __YELLOW__{warning}__RESET__", color_enabled))
            msg = (
                "__GREEN__Successfully rebuilt vector store__RESET__: "
                f"indexed __CYAN__{indexed_count}__RESET__ / {total_files} files; "
                f"entries created __GREEN__{entries_created}__RESET__, entries deleted __YELLOW__{entries_deleted}__RESET__."
            )
            print(render_placeholders(msg, color_enabled))
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            msg = f"__RED__Error rebuilding vector store: {exc}__RESET__"
            print(render_placeholders(msg, color_enabled))
        return 1
