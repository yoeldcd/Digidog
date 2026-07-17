# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to incrementally update the ChromaDB vector store."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from brain.infrastructure.vectorstores.recovery import (
    embedding_unavailable_guide,
    is_embedding_unavailable_error,
    requires_entry_metadata_refresh,
)
from brain.application.knowledge.vector_sync import sync_all_knowledge_vectorstores
from brain.application.memory.paths import MEMORY_ROOT
from brain.infrastructure.vectorstores.manager import VectorStoreManager
from brain.infrastructure.vectorstores.messages import sync_all_message_vectors
from brain.infrastructure.vectorstores.pictures import sync_picture_vectors
from brain.presentation.terminal import render_placeholders, log_step



def handle(args: argparse.Namespace) -> int:
    """Incremental update vectorstore."""
    color_enabled = getattr(args, "color", False)
    log_step(args, '[1/2] Scanning for changes...')
    try:
        manager = VectorStoreManager()

        # Get existing items from collection to check mtimes
        # We query all items in the collection to extract metadata
        existing = manager.collection.get(include=["metadatas"])

        # Build map of chunk_id -> indexed mtime
        indexed_mtimes = {}
        indexed_metadata = {}
        if existing and existing["ids"]:
            for i in range(len(existing["ids"])):
                cid = existing["ids"][i]
                meta = existing["metadatas"][i] if existing["metadatas"] else {}
                indexed_mtimes[cid] = meta.get("mtime", 0.0)
                indexed_metadata[cid] = dict(meta or {})

        memory_dir = Path(MEMORY_ROOT)
        md_files = []
        for p in memory_dir.rglob("*.md"):
            if p.parent == memory_dir:
                continue
            md_files.append(p)

        updated_count = 0
        deleted_count = 0
        entries_created = 0
        entries_deleted = 0
        file_stats = []
        knowledge_stats = []
        knowledge_warnings = []
        total_discovered = len(md_files)

        # Track which file-level IDs are active to discover deleted files
        active_keys = set()

        log_step(args, '[2/2] Updating modified entries...')
        for p in md_files:
            rel = p.relative_to(memory_dir)
            parts = rel.parts

            if len(parts) >= 2:
                category = ".".join(parts[:-1])
                key = p.stem
            else:
                continue

            active_keys.add((category, key))

            # File mtime
            file_mtime = p.stat().st_mtime

            # Check if this file has any chunks in Chroma, and if the mtimes match
            # Simple check: check if the base ID (category.key) mtime matches.
            # If not indexed, or mtime is different, we update.
            base_id = f"{category}.{key}"

            # We look for any key in indexed_mtimes that starts with f"{category}.{key}"
            # and verify if its indexed mtime matches the file's current mtime.
            needs_update = True

            # Find all indexed chunks matching this file prefix
            chunks_for_file = {cid: mtime for cid, mtime in indexed_mtimes.items() if cid == base_id or cid.startswith(f"{base_id}#")}

            if chunks_for_file:
                # If all chunks have the same mtime as the file, we can skip
                all_match = all(abs(indexed_mtime - file_mtime) < 0.01 for indexed_mtime in chunks_for_file.values())
                metadata_current = not any(
                    requires_entry_metadata_refresh(category=category, metadata=indexed_metadata.get(chunk_id))
                    for chunk_id in chunks_for_file
                )
                if all_match and metadata_current:
                    needs_update = False

            if needs_update:
                content = p.read_text(encoding="utf-8")
                stats = manager.add_or_update_file(category, key, content)
                file_stats.append(stats)
                entries_created += int(stats.get("entries_created") or 0)
                entries_deleted += int(stats.get("entries_deleted") or 0)
                updated_count += 1
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

        # Clean up deleted files from vector store
        # Extract unique (category, key) pairs from indexed items
        indexed_files = set()
        if existing and existing["metadatas"]:
            for meta in existing["metadatas"]:
                if meta and "category" in meta and "key" in meta:
                    indexed_files.add((meta["category"], meta["key"]))

        for cat, k in indexed_files:
            if (cat, k) not in active_keys:
                removed_entries = manager.delete_file(cat, k)
                entries_deleted += removed_entries
                deleted_count += 1
                if not args.json and getattr(args, "verbose_log", False):
                    print(
                        render_placeholders(
                            f"  removed __CYAN__memory/{cat.replace('.', '/')}/{k}.md__RESET__: entries __YELLOW__{removed_entries}__RESET__",
                            color_enabled,
                        ),
                    )

        knowledge_stats, knowledge_warnings = sync_all_knowledge_vectorstores()
        message_stats = sync_all_message_vectors()
        picture_stats = sync_picture_vectors()

        if args.json:
            print(json.dumps({
                "ok": True,
                "message": "Vector store updated incrementally.",
                "updated_files": updated_count,
                "deleted_files": deleted_count,
                "entries_created": entries_created,
                "entries_deleted": entries_deleted,
                "total_active": total_discovered,
                "files": file_stats,
                "knowledge": knowledge_stats,
                "messages": message_stats,
                "pictures": picture_stats,
                "warnings": knowledge_warnings,
            }, ensure_ascii=False))
        else:
            for warning in knowledge_warnings:
                print(render_placeholders(f"  __YELLOW__{warning}__RESET__", color_enabled))
            msg = (
                "__GREEN__Vector store updated__RESET__: "
                f"updated __CYAN__{updated_count}__RESET__, deleted __CYAN__{deleted_count}__RESET__ / {total_discovered} files; "
                f"entries created __GREEN__{entries_created}__RESET__, entries deleted __YELLOW__{entries_deleted}__RESET__."
            )
            print(render_placeholders(msg, color_enabled))
        return 0
    except Exception as exc:
        is_embedding_failure = is_embedding_unavailable_error(exc)
        if is_embedding_failure:
            setattr(args, "embedding_unavailable", str(exc))
        if args.json:
            payload = {"ok": False, "error": str(exc)}
            if is_embedding_failure:
                payload["embedding_unavailable"] = True
                payload["guide"] = embedding_unavailable_guide("python .\\$agent\\scripts\\brain.py update-vectorstore")
            print(json.dumps(payload, ensure_ascii=False))
        else:
            if is_embedding_failure:
                if not getattr(args, "best_effort", False):
                    print(render_placeholders(
                        embedding_unavailable_guide("python .\\$agent\\scripts\\brain.py update-vectorstore"),
                        color_enabled,
                    ))
            else:
                msg = f"__RED__Error updating vector store: {exc}__RESET__"
                print(render_placeholders(msg, color_enabled))
        if getattr(args, "best_effort", False) and is_embedding_failure:
            return 0
        return 1
