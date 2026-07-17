# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to rebuild the ChromaDB vector store from scratch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from brain.application.knowledge.vector_sync import sync_all_knowledge_vectorstores
from brain.application.memory.paths import MEMORY_ROOT
from brain.infrastructure.vectorstores.manager import VectorStoreManager
from brain.infrastructure.vectorstores.messages import sync_all_message_vectors
from brain.infrastructure.vectorstores.pictures import sync_picture_vectors
from brain.infrastructure.vectorstores.generations import replace_vectorstore_generation, validate_vectorstore_generation
from brain.infrastructure.runtime.paths import get_vectorstore_dir
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

    log_step(args, '[1/2] Building a temporary semantic database generation...')
    try:
        active_path: Path = get_vectorstore_dir(scope="global", create=False)
        generation_stats = replace_vectorstore_generation(
            active_path=active_path,
            builder=lambda generation_path: build_vectorstore_generation(
                generation_path=generation_path,
                args=args,
                color_enabled=color_enabled,
            ),
            validator=lambda generation_path: validate_vectorstore_generation(
                generation_path=generation_path,
                expected_collections={"memories", "knowledge", "messages", "pictures"},
            ),
        )
        build_stats = dict(generation_stats["build"])

        if args.json:
            print(json.dumps({
                "ok": True,
                "message": "Vector store rebuilt successfully.",
                **build_stats,
                "generation": generation_stats,
            }, ensure_ascii=False))
        else:
            msg = (
                "__GREEN__Successfully rebuilt vector store__RESET__: "
                f"indexed __CYAN__{build_stats['indexed_files']}__RESET__ / {build_stats['total_discovered']} files; "
                f"entries created __GREEN__{build_stats['entries_created']}__RESET__; "
                "the prior generation was retired after the validated atomic swap."
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


def build_vectorstore_generation(
    generation_path: Path,
    args: argparse.Namespace,
    color_enabled: bool,
) -> dict[str, object]:
    """Build every global vector collection inside an isolated directory."""
    manager = VectorStoreManager(db_path=generation_path, collection_name="memories")
    indexed_count: int = 0
    entries_created: int = 0
    file_stats: list[dict[str, int | str]] = []
    memory_dir = Path(MEMORY_ROOT)
    md_files: list[Path] = [path for path in memory_dir.rglob("*.md") if path.parent != memory_dir]
    log_step(args, '[2/2] Indexing all memory, knowledge, message, and picture records...')
    try:
        for path in md_files:
            relative_path: Path = path.relative_to(memory_dir)
            if len(relative_path.parts) < 2:
                continue
            category: str = ".".join(relative_path.parts[:-1])
            stats = manager.add_or_update_file(category, path.stem, path.read_text(encoding="utf-8"))
            file_stats.append(stats)
            entries_created += int(stats.get("entries_created") or 0)
            indexed_count += 1
            if not args.json and getattr(args, "verbose_log", False):
                print(
                    render_placeholders(
                        "  vectorized __CYAN__{path}__RESET__: entries __GREEN__{entries}__RESET__".format(
                            path=stats.get("path") or path.as_posix(),
                            entries=stats.get("entries_created") or 0,
                        ),
                        color_enabled,
                    ),
                )
    finally:
        manager.close()
    knowledge_stats, knowledge_warnings = sync_all_knowledge_vectorstores(vectorstore_path=generation_path)
    if knowledge_warnings:
        raise RuntimeError("; ".join(knowledge_warnings))
    message_stats = sync_all_message_vectors(db_path=generation_path, reset=False)
    picture_stats = sync_picture_vectors(db_path=generation_path, reset=False)
    return {
        "indexed_files": indexed_count,
        "entries_created": entries_created,
        "entries_deleted": 0,
        "total_discovered": len(md_files),
        "files": file_stats,
        "knowledge": knowledge_stats,
        "messages": message_stats,
        "pictures": picture_stats,
        "warnings": [],
    }
