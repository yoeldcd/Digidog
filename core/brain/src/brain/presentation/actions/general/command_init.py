"""Initialize session: run workspace checks and hydrate context."""

from __future__ import annotations

import argparse
import os
from pathlib import Path




def _workspace_root() -> Path:
    """Return the workspace root used by local runtime stores."""
    return Path(os.environ.get("WORKSPACE_ROOT", ".")).resolve()


def _print_detail(args: argparse.Namespace, message: str) -> None:
    """Print one indented init detail line using the active color policy."""
    from brain.presentation.terminal import render_placeholders

    if not getattr(args, "verbose_log", False):
        return
    color_enabled = getattr(args, "color", False)
    print(render_placeholders(f"  {message}", color_enabled), flush=True)


def _print_progress(args: argparse.Namespace, message: str = "") -> None:
    """Print init progress-only text when verbose logging is enabled."""
    if getattr(args, "verbose_log", False):
        print(message, flush=True)


def _print_object(args: argparse.Namespace, label: str, identifier: str, detail: str = "") -> None:
    """Print one verbose object-level init diagnostic."""
    suffix = f" {detail}" if detail else ""
    _print_detail(args, f"{label} __CYAN__{identifier}__RESET__{suffix}")


def _log_initialization_step(args: argparse.Namespace, message: str) -> None:
    """Print one init-owned progress step with an explicit namespace."""
    from brain.presentation.terminal import log_step

    log_step(args, message, task="initialization")


def _memory_source_paths() -> list[str]:
    """Return active memory markdown source paths."""
    from brain.application.memory.diagnostics import load_ignore_list
    from brain.application.memory.paths import MEMORY_ROOT, ensure_memory_root

    ensure_memory_root()
    ignored = load_ignore_list()
    source_paths: list[str] = []
    for path in MEMORY_ROOT.rglob("*.md"):
        if path.parent == MEMORY_ROOT or path.name in ignored:
            continue
        rel_path = path.relative_to(MEMORY_ROOT)
        if any(part.startswith(".") or part in ignored for part in rel_path.parts):
            continue
        source_paths.append(f"memory/{rel_path.as_posix()}")
    return sorted(source_paths)


def _memory_registry_records() -> list[object]:
    """Return active memory source-registry records."""
    from brain.infrastructure.sources.registry.records import list_source_registry_records

    return list_source_registry_records(scope="global", root_prefix="memory", active_only=True)


def _log_source_paths(workspace_root: Path) -> tuple[list[str], list[str]]:
    """Return canonical and legacy workspace log source paths."""
    from brain.application.logs.parsing import glob_log_and_md_files, is_canonical_log_file

    logs_dir = workspace_root / "$agent" / "logs"
    if not logs_dir.exists():
        return [], []
    log_files = glob_log_and_md_files(logs_dir)
    canonical_paths: list[str] = []
    legacy_paths: list[str] = []
    for log_file in log_files:
        rel_path = f"$agent/logs/{log_file.relative_to(logs_dir).as_posix()}"
        if is_canonical_log_file(log_file):
            canonical_paths.append(rel_path)
        else:
            legacy_paths.append(rel_path)
    return sorted(canonical_paths), sorted(legacy_paths)


def handle(args: argparse.Namespace) -> int:
    """Run workspace checks, update all indexes, and print context payload in sequence."""
    from brain.presentation.actions.general import command_check_workspace, command_get_context
    from brain.presentation.actions.logs import command_update_log_index
    from brain.presentation.actions.memory import command_update_memory_index
    from brain.presentation.actions.vectorstore import command_update_vectorstore
    from brain.presentation.terminal import render_placeholders
    from brain.infrastructure.runtime.migration_service import migrate_brain_runtime_stores
    from brain.application.backlog.service import migrate_legacy_backlog
    from brain.application.logs.store import get_logs_database_path, log_database_summary

    color_enabled = getattr(args, "color", False)
    workspace_root = _workspace_root()
    _print_object(args, "workspace root", workspace_root.as_posix())
    _print_object(args, "logs database", (workspace_root / "$agent" / "database" / "brain_logs.db").as_posix())

    # 0. Migrate legacy runtime stores
    _log_initialization_step(args, "[1/7] Migrating runtime stores...")
    _log_initialization_step(args, "[1/3] Resolving current database layout...")
    _log_initialization_step(args, "[2/3] Inspecting and migrating legacy stores...")
    migration_report = migrate_brain_runtime_stores()
    _log_initialization_step(args, "[3/3] Reporting migration results...")
    if migration_report.actions:
        _print_progress(
            args,
            render_placeholders(f"__GREEN__Runtime store migrations: {len(migration_report.actions)} action(s).__RESET__", color_enabled),
        )
        for action in migration_report.actions:
            target = f" -> {action.target}" if action.target else ""
            detail = f" ({action.detail})" if action.detail else ""
            _print_detail(args, f"{action.action} __CYAN__{action.source}{target}__RESET__{detail}")
    else:
        _print_progress(args, render_placeholders("__DIM__Runtime stores already use current database layout.__RESET__", color_enabled))
    for warning in migration_report.warnings:
        print(render_placeholders(f"__YELLOW__Runtime migration warning: {warning}__RESET__", color_enabled))

    _print_progress(args)

    # 1. Workspace checks
    _log_initialization_step(args, "[2/7] Validating memory structure...")
    _log_initialization_step(args, "[1/3] Loading memory validation rules...")
    memory_source_paths = _memory_source_paths()
    memory_domains = {path.split("/", 2)[1] for path in memory_source_paths if "/" in path}
    memory_source_count = len(memory_source_paths)
    memory_domain_count = len(memory_domains)
    _print_object(args, "memory root", "memory")
    for source_path in memory_source_paths:
        _print_object(args, "memory validation source", source_path)
    _log_initialization_step(args, "[2/3] Scanning memory tree...")
    check_args = argparse.Namespace(
        json=False,
        color=getattr(args, "color", False),
        verbose_log=getattr(args, "verbose_log", False),
    )
    ret = command_check_workspace.handle(check_args)
    if ret != 0:
        return ret
    _log_initialization_step(args, "[3/3] Reporting memory validation coverage...")
    _print_detail(
        args,
        "memory scan covered __CYAN__{sources}__RESET__ markdown files across __CYAN__{domains}__RESET__ top-level domains.".format(
            sources=memory_source_count,
            domains=memory_domain_count,
        ),
    )

    _print_progress(args)

    # 2. Update memory index
    _log_initialization_step(args, "[3/7] Updating memory index...")
    _log_initialization_step(args, "[1/3] Discovering memory sources...")
    _print_detail(
        args,
        "discovered __CYAN__{sources}__RESET__ source files across __CYAN__{domains}__RESET__ domains.".format(
            sources=memory_source_count,
            domains=memory_domain_count,
        ),
    )
    _log_initialization_step(args, "[2/3] Refreshing source registry...")
    _print_object(args, "source registry", "global:memory")
    update_mem_args = argparse.Namespace(
        json=False,
        color=getattr(args, "color", False),
        verbose_log=getattr(args, "verbose_log", False),
    )
    ret = command_update_memory_index.handle(update_mem_args)
    if ret != 0:
        return ret
    registry_records = _memory_registry_records()
    indexed_sources = len(registry_records)
    indexed_entries = sum(int(record.entries or 0) for record in registry_records)
    _log_initialization_step(args, "[3/3] Reporting memory index coverage...")
    for record in registry_records:
        _print_object(
            args,
            "memory registry row",
            record.path,
            f"type={record.source_type} entries={record.entries} size={record.size} lines={record.lines}",
        )
    _print_detail(
        args,
        "memory registry tracks __CYAN__{sources}__RESET__ active files with __GREEN__{entries}__RESET__ detected entries.".format(
            sources=indexed_sources,
            entries=indexed_entries,
        ),
    )

    _print_progress(args)

    # 3. Update logs index
    _log_initialization_step(args, "[4/7] Migrating workspace logs to SQLite...")
    _log_initialization_step(args, "[1/4] Discovering workspace log sources...")
    canonical_log_paths, legacy_log_paths = _log_source_paths(workspace_root)
    canonical_logs = len(canonical_log_paths)
    legacy_logs = len(legacy_log_paths)
    total_logs = canonical_logs + legacy_logs
    for source_path in canonical_log_paths:
        _print_object(args, "canonical log source", source_path)
    for source_path in legacy_log_paths:
        _print_object(args, "legacy log source", source_path)
    _print_detail(
        args,
        "found __CYAN__{canonical}__RESET__ canonical logs and __YELLOW__{legacy}__RESET__ legacy candidates / {total} files.".format(
            canonical=canonical_logs,
            legacy=legacy_logs,
            total=total_logs,
        ),
    )
    _log_initialization_step(args, "[2/4] Delegating migration to update-log-index...")
    update_log_args = argparse.Namespace(
        mode=None,
        fix=True,
        color=getattr(args, "color", False),
        verbose_log=getattr(args, "verbose_log", False),
        log_task="initialization",
    )
    old_log_workspace_root = command_update_log_index.WORKSPACE_ROOT
    command_update_log_index.WORKSPACE_ROOT = workspace_root
    try:
        ret = command_update_log_index.handle(update_log_args)
    finally:
        command_update_log_index.WORKSPACE_ROOT = old_log_workspace_root
    if ret != 0:
        return ret

    _log_initialization_step(args, "[3/5] Migrating legacy backlog tasks into the logs database...")
    backlog_report = migrate_legacy_backlog(workspace_root=workspace_root)
    _print_detail(
        args,
        "backlog migration imported __GREEN__{imported}__RESET__ task(s); __CYAN__{existing}__RESET__ persisted task(s) kept unchanged.".format(
            imported=backlog_report.imported,
            existing=backlog_report.existing,
        ),
    )

    _log_initialization_step(args, "[4/5] Reading SQLite latest-index projection...")
    _print_object(
        args,
        "logs DB projection",
        f"{get_logs_database_path(workspace_root=workspace_root).as_posix()}::log_index_latest",
    )
    entry_count, domain_count, latest_count = log_database_summary(workspace_root=workspace_root)
    _print_detail(
        args,
        "logs DB tracks __GREEN__{entries}__RESET__ entries across __CYAN__{domains}__RESET__ domains with __CYAN__{latest}__RESET__ latest-index rows.".format(
            entries=entry_count,
            domains=domain_count,
            latest=latest_count,
        ),
    )
    _log_initialization_step(args, "[5/5] Log and backlog migration delegation complete...")

    _print_progress(args)

    # 4. Update vector store
    _log_initialization_step(args, "[5/7] Updating vector store...")
    _print_object(args, "vector collection", "global:memories")
    _print_object(args, "vector collection", "global:knowledge")
    _print_object(args, "vector collection", "local:knowledge")
    update_vs_args = argparse.Namespace(
        json=False,
        color=getattr(args, "color", False),
        verbose_log=getattr(args, "verbose_log", False),
        best_effort=True,
    )
    ret = command_update_vectorstore.handle(update_vs_args)
    if ret != 0:
        return ret
    embedding_warning = getattr(update_vs_args, "embedding_unavailable", None)
    if embedding_warning:
        setattr(args, "embedding_unavailable", embedding_warning)

    _print_progress(args)

    # 5. Ensure knowledge graph runtime
    _log_initialization_step(args, "[6/7] Preparing knowledge graph runtime...")
    try:
        from brain.infrastructure.database.knowledge.repository import KnowledgeRepository

        _log_initialization_step(args, "[1/3] Opening global knowledge repository...")
        _print_object(args, "knowledge repository", "global")
        KnowledgeRepository(scope="global")
        _log_initialization_step(args, "[2/3] Opening local knowledge repository...")
        _print_object(args, "knowledge repository", "local")
        KnowledgeRepository(scope="local")
        _log_initialization_step(args, "[3/3] Reporting knowledge runtime status...")
        _print_detail(args, "__GREEN__Knowledge graph runtime ready__RESET__: global and local repositories opened.")
    except Exception as exc:
        print(f"Knowledge graph runtime warning: {exc}")

    _print_progress(args, "\n" + "=" * 60 + "\n")

    # 6. Hydrate context
    _log_initialization_step(args, "[7/7] Hydrating session context...")
    result = command_get_context.handle(args)
    context_payload = getattr(args, "json_payload", None)
    args.json_payload = {
        "ok": result == 0,
        "command": "init",
        "workspaceRoot": workspace_root.as_posix(),
        "migration": {
            "actions": [
                {
                    "action": action.action,
                    "source": action.source,
                    "target": action.target,
                    "detail": action.detail,
                }
                for action in migration_report.actions
            ],
            "warnings": list(migration_report.warnings),
        },
        "memory": {
            "sources": indexed_sources,
            "domains": memory_domain_count,
            "entries": indexed_entries,
        },
        "logs": {
            "entries": entry_count,
            "domains": domain_count,
            "latestRows": latest_count,
            "legacySources": legacy_logs,
            "canonicalSources": canonical_logs,
        },
        "backlog": {
            "imported": backlog_report.imported,
            "existing": backlog_report.existing,
        },
        "embeddingWarning": getattr(args, "embedding_unavailable", None),
        "context": context_payload,
    }
    return result
