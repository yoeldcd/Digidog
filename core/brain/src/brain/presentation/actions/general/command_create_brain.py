"""CLI action for creating a workspace-local brain entrypoint."""

from __future__ import annotations

# Standard Libraries Imports
import sys
from pathlib import Path

# Application Modules Imports
from brain.application.workspace.bootstrap_service import (
    create_workspace_brain_entrypoint,
    ensure_workspace_readme,
    ensure_workspace_structure,
    inspect_git_repository,
    migrate_legacy_agent_directory,
    refresh_workspace_logs_database,
    validate_workspace_path,
)
from brain.presentation.terminal import log_step, render_placeholders


def handle(args) -> int:
    """
    Create `$agent/scripts/brain.py` inside a target workspace.

    Args:
        args: Parsed CLI arguments.

    Returns:
        int: Process exit code.
    """
    workspace_value = args.workspace if args.workspace is not None else args.workspace_path
    if workspace_value is None:
        print("Error: workspace must be provided via --workspace or compact positional form.", file=sys.stderr)
        return 1

    workspace = Path(workspace_value).resolve()
    workspace_error: str | None = validate_workspace_path(path=workspace)
    if workspace_error:
        print(f"Error: {workspace_error}\nPass the project root, e.g. create-brain <workspace-root>", file=sys.stderr)
        return 1

    color_enabled = getattr(args, "color", False)
    limit = getattr(args, "limit", 10)
    _migrate_legacy_agent_dir(workspace=workspace, color_enabled=color_enabled, limit=limit)

    log_step(args, "[1/4] Verifying Git repository status...")
    git_result = inspect_git_repository(workspace=workspace)
    if not git_result.has_git_repository:
        warn_msg = (
            f"__YELLOW__[WARNING] Target workspace '{workspace}' is not a Git repository. "
            "It is highly recommended to run 'git init' first.__RESET__"
        )
        print(render_placeholders(warn_msg, color_enabled), flush=True)
    elif git_result.has_changes:
        info_msg = "__YELLOW__[INFO] Target repository has unstaged/uncommitted changes. Please review them.__RESET__"
        print(render_placeholders(info_msg, color_enabled), flush=True)

    log_step(args, "[2/4] Setting up workspace directories...")
    structure_result = ensure_workspace_structure(workspace=workspace)
    readme_created = ensure_workspace_readme(workspace=workspace)
    if readme_created:
        print("Created workspace guidelines at: $agent/README.md", flush=True)

    log_step(args, "[3/4] Verifying logs database integrity...")
    database_path = None
    try:
        database_path = refresh_workspace_logs_database(workspace=workspace)
        print(f"Verified logs database projection at: {database_path.relative_to(workspace)}", flush=True)
    except Exception as exc:
        warn_msg = f"__RED__[WARNING] Logs integrity check encountered issues: {exc}__RESET__"
        print(render_placeholders(warn_msg, color_enabled), file=sys.stderr, flush=True)

    log_step(args, "[4/4] Cloning core/core_cli.py as workspace brain.py...")
    try:
        entrypoint_result = create_workspace_brain_entrypoint(
            workspace=workspace,
            scripts_dir=structure_result.scripts_dir,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr, flush=True)
        return 1

    print(f"Cloned factory core_cli.py -> {entrypoint_result.destination.relative_to(workspace)}")
    print(f"WORKSPACE_ROOT = {entrypoint_result.workspace_root_text}")
    from brain.infrastructure.runtime.paths import register_project_path
    register_project_path(workspace)
    args.json_payload = {
        "ok": True,
        "command": "create-brain",
        "workspace": workspace.as_posix(),
        "git": {
            "repository": git_result.has_git_repository,
            "hasChanges": git_result.has_changes,
        },
        "structure": {
            "scripts": structure_result.scripts_dir.as_posix(),
            "logs": structure_result.logs_dir.as_posix(),
            "data": structure_result.data_dir.as_posix(),
            "readmeCreated": readme_created,
        },
        "database": database_path.as_posix() if database_path is not None else None,
        "entrypoint": {
            "path": entrypoint_result.destination.as_posix(),
            "workspaceRoot": entrypoint_result.workspace_root_text,
        },
        "registered": True,
    }
    return 0


def _migrate_legacy_agent_dir(workspace: Path, color_enabled: bool, limit: int) -> None:
    """
    Migrate a legacy `.agent` directory and print bounded status lines.

    Args:
        workspace (Path): Workspace root.
        color_enabled (bool): Whether color placeholders should render.
        limit (int): Maximum migration lines to print before truncation.
    """
    legacy_agent_dir: Path = workspace / ".agent"
    target_agent_dir: Path = workspace / "$agent"
    if not legacy_agent_dir.exists() or not legacy_agent_dir.is_dir():
        return

    msg = "__CYAN__[INFO] Legacy '.agent' directory detected. Migrating contents safely to '$agent'...__RESET__"
    print(render_placeholders(msg, color_enabled))
    try:
        logs = migrate_legacy_agent_directory(legacy_dir=legacy_agent_dir, target_dir=target_agent_dir)
    except Exception as exc:
        err_msg = f"__RED__[ERROR] Failed to safely migrate legacy '.agent' directory: {exc}__RESET__"
        print(render_placeholders(err_msg, color_enabled), file=sys.stderr)
        return

    visible_logs = logs
    has_more = False
    if limit > 0 and len(logs) > limit:
        visible_logs = logs[:limit]
        has_more = True

    for log_line in visible_logs:
        print(render_placeholders(_migration_status_line(line=log_line), color_enabled))
    if has_more:
        more_msg = f"__DIM__  - ... and {len(logs) - limit} more files.__RESET__"
        print(render_placeholders(more_msg, color_enabled))

    success_msg = "__GREEN__[SUCCESS] Safely migrated legacy '.agent' directory to '$agent'.__RESET__"
    print(render_placeholders(success_msg, color_enabled))


def _migration_status_line(line: str) -> str:
    """
    Return a colorized migration status line.

    Args:
        line (str): Raw status line.

    Returns:
        str: Placeholder-formatted status line.
    """
    if "ERROR" in line:
        return f"__RED__{line}__RESET__"
    if "OVERWRITE" in line:
        return f"__YELLOW__{line}__RESET__"
    return f"__GREEN__{line}__RESET__"
