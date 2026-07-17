# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Application services for creating a workspace-local brain entrypoint."""

from __future__ import annotations

# Standard Libraries Imports
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Application Modules Imports
from brain.application.logs.index_service import migrate_log_files_to_database
from brain.application.logs.store import get_logs_database_path
from brain.infrastructure.runtime.paths import get_core_cli_path, get_core_root
from brain.infrastructure.messages.repository import MessageRepository


AGENT_DIRECTORY_NAMES = {"$agent", ".agent", "agent"}
"""Directory names that identify agent metadata directories, not workspace roots."""


WORKSPACE_README_TEXT = (
    "# Agent Workspace Guidelines\n\n"
    "Welcome to this workspace. Follow these agent operating rules:\n\n"
    "## 1. Local Entrypoint Usage\n"
    "Always use the local entrypoint located at `$agent/scripts/brain.py` to interact with memory and logs. "
    "Do NOT use the consumer factory `core/core_cli.py` for normal Brain commands.\n\n"
    "## 2. Workspace Logs\n"
    "All progress logs must be written through the DB-backed brain CLI.\n"
    "- To append a log: `python $agent/scripts/brain.py append-log -d <domain> -t <title> ...`\n"
    "- Use `export-logs` when Markdown files are needed for external tools.\n"
    "- Never edit the logs database or exported log files manually.\n\n"
    "## 3. Environment & Security\n"
    "Ensure your work is committed and tracked. If git is not initialized or there are unstaged changes, "
    "confirm with the user before proceeding.\n"
)
"""Default workspace README content."""


WORKSPACE_CODEX_CONFIG_TEXT = """# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

# --------------------------------------------------------------------------- #
# --- WOSP CODEX POLICY BINDING --------------------------------------------- #
# --------------------------------------------------------------------------- #
# This project-local file defines and selects the agent-specific profile.
# Codex requires default_permissions when a custom profile is declared. Auto
# Review handles escalations while project trust remains owned by Codex.

approval_policy = "on-request"
approvals_reviewer = "auto_review"
default_permissions = "{{AGENT_PROFILE_NAME}}"
allow_login_shell = false

[permissions.{{AGENT_PROFILE_NAME}}]
description = "Agent-local access for this WoSP and its canonical agent directory."
extends = ":read-only"

[permissions.{{AGENT_PROFILE_NAME}}.filesystem]
"{{AGENT_DIR}}" = "write"
"~/.ssh" = "deny"
"~/.aws" = "deny"
"~/.azure" = "deny"
glob_scan_max_depth = 6

[permissions.{{AGENT_PROFILE_NAME}}.filesystem.":workspace_roots"]
"." = "write"
".env" = "deny"
".env.*" = "deny"
"*.env" = "deny"
"**/.env" = "deny"
"**/.env.*" = "deny"
"**/*.env" = "deny"
"""
"""Restrictive project-local Codex configuration created for every WoSP."""


WORKSPACE_CODEX_RULES_TEXT = r'''# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

# Brain is the agent-owned control plane. This narrow prefix permits every
# Brain subcommand to run outside the sandbox without review, including local
# services and model-backed commands that require network access. It does not
# authorize generic Python or any other script.
prefix_rule(
    pattern = ["py", ".\\$agent\\scripts\\brain.py"],
    decision = "allow",
    justification = "The workspace Brain CLI is an agent-owned trusted control plane.",
    match = [
        "py .\\$agent\\scripts\\brain.py avatar-service-status --json",
        "py .\\$agent\\scripts\\brain.py query example --json",
    ],
    not_match = [
        "py arbitrary.py",
        "py -c print('not Brain')",
    ],
)
'''
"""Project-local command rule that trusts only the Brain CLI prefix."""


@dataclass(frozen=True)
class GitInspectionResult:
    """Git repository inspection result."""

    has_git_repository: bool
    has_changes: bool


@dataclass(frozen=True)
class WorkspaceStructureResult:
    """Created workspace metadata paths."""

    scripts_dir: Path
    logs_dir: Path
    data_dir: Path
    messages_database: Path


@dataclass(frozen=True)
class BrainEntrypointResult:
    """Created workspace brain entrypoint metadata."""

    destination: Path
    workspace_root_text: str


def validate_workspace_path(path: Path) -> str | None:
    """
    Return an error string if `path` points to agent metadata instead of a workspace root.

    Args:
        path (Path): Candidate workspace path.

    Returns:
        str | None: Error text when invalid.
    """
    name: str = path.name.lower().lstrip("$")
    if name in AGENT_DIRECTORY_NAMES:
        return f"'{path}' looks like a $agent directory, not a workspace root."
    if name == "scripts" and path.parent.name.lower().lstrip("$") in AGENT_DIRECTORY_NAMES:
        return f"'{path}' looks like $agent/scripts, not a workspace root."
    return None


def migrate_legacy_agent_directory(legacy_dir: Path, target_dir: Path) -> list[str]:
    """
    Move legacy `.agent` contents into `$agent`.

    Args:
        legacy_dir (Path): Legacy metadata directory.
        target_dir (Path): Current metadata directory.

    Returns:
        list[str]: Human-readable migration status lines.
    """
    if not legacy_dir.exists() or not legacy_dir.is_dir():
        return []
    logs: list[str] = migrate_legacy_agent_contents(
        legacy_dir=legacy_dir,
        target_dir=target_dir,
        current_subdir=legacy_dir,
    )
    shutil.rmtree(str(legacy_dir))
    return logs


def migrate_legacy_agent_contents(legacy_dir: Path, target_dir: Path, current_subdir: Path) -> list[str]:
    """
    Recursively move contents from legacy metadata to current metadata.

    Args:
        legacy_dir (Path): Source directory for this recursion level.
        target_dir (Path): Target directory for this recursion level.
        current_subdir (Path): Root used for relative status lines.

    Returns:
        list[str]: Human-readable migration status lines.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    logs: list[str] = []
    for item in legacy_dir.iterdir():
        target_item: Path = target_dir / item.name
        rel_path: str = item.relative_to(current_subdir).as_posix()
        if item.is_dir():
            logs.extend(
                migrate_legacy_agent_contents(
                    legacy_dir=item,
                    target_dir=target_item,
                    current_subdir=current_subdir,
                ),
            )
            continue

        status: str = move_legacy_agent_file(item=item, target_item=target_item)
        logs.append(f"  - {rel_path} -> ({status})")
    return logs


def move_legacy_agent_file(item: Path, target_item: Path) -> str:
    """
    Move one legacy metadata file, preserving a backup when overwriting.

    Args:
        item (Path): Source file.
        target_item (Path): Target file.

    Returns:
        str: Move status label.
    """
    status: str = "SUCCESS"
    if target_item.exists():
        try:
            if item.read_bytes() != target_item.read_bytes():
                backup_file: Path = target_item.with_suffix(target_item.suffix + ".bak")
                shutil.copy2(target_item, backup_file)
                status = "OVERWRITE"
        except Exception as exc:
            return f"ERROR: {exc}"

    try:
        shutil.move(str(item), str(target_item))
    except Exception as exc:
        return f"ERROR: {exc}"
    return status


def inspect_git_repository(workspace: Path) -> GitInspectionResult:
    """
    Inspect git availability and dirty state for a workspace.

    Args:
        workspace (Path): Workspace root.

    Returns:
        GitInspectionResult: Repository presence and changed-file status.
    """
    git_dir: Path = workspace / ".git"
    if not git_dir.exists():
        return GitInspectionResult(has_git_repository=False, has_changes=False)
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return GitInspectionResult(has_git_repository=True, has_changes=False)
    return GitInspectionResult(has_git_repository=True, has_changes=result.returncode == 0 and bool(result.stdout.strip()))


def ensure_workspace_structure(workspace: Path) -> WorkspaceStructureResult:
    """
    Create required workspace metadata directories.

    Args:
        workspace (Path): Workspace root.

    Returns:
        WorkspaceStructureResult: Created directory paths.
    """
    scripts_dir: Path = workspace / "$agent" / "scripts"
    logs_dir: Path = workspace / "$agent" / "logs"
    data_dir: Path = workspace / "$agent" / "data"
    database_dir: Path = workspace / "$agent" / "database"
    for directory in (scripts_dir, logs_dir, data_dir, database_dir):
        directory.mkdir(parents=True, exist_ok=True)
    messages_database: Path = MessageRepository(
        consumer_path=workspace,
        require_registered=False,
    ).initialize()
    return WorkspaceStructureResult(
        scripts_dir=scripts_dir,
        logs_dir=logs_dir,
        data_dir=data_dir,
        messages_database=messages_database,
    )


def ensure_workspace_readme(workspace: Path) -> bool:
    """
    Create `$agent/README.md` when missing.

    Args:
        workspace (Path): Workspace root.

    Returns:
        bool: True when the README was created.
    """
    readme_file: Path = workspace / "$agent" / "README.md"
    if readme_file.exists():
        return False
    readme_file.write_text(WORKSPACE_README_TEXT, encoding="utf-8")
    return True


def ensure_workspace_codex_config(workspace: Path, agent_name: str, agent_dir: Path) -> bool:
    """
    Create a restrictive project-local `.codex/config.toml` when missing.

    The local file only selects the global permission profile and approval
    behavior. It deliberately defines no permissions, writable roots, network
    access, command rules, or environment-variable overrides.

    Args:
        workspace (Path): Workspace root.
        agent_name (str): Canonical agent name used to derive the local profile.
        agent_dir (Path): Canonical agent directory required by Brain and avatar services.

    Returns:
        bool: True when the configuration file was created.
    """
    config_file: Path = workspace / ".codex" / "config.toml"
    if config_file.exists():
        return False
    config_file.parent.mkdir(parents=True, exist_ok=True)
    normalized_name = re.sub(r"[^a-z0-9]+", "_", agent_name.lstrip("@").casefold()).strip("_")
    if not normalized_name:
        raise ValueError("agent_name cannot derive a local Codex permission profile")
    content = WORKSPACE_CODEX_CONFIG_TEXT.replace(
        "{{AGENT_PROFILE_NAME}}",
        f"{normalized_name}_workspace_guard",
    ).replace(
        "{{AGENT_DIR}}",
        agent_dir.resolve().as_posix(),
    )
    config_file.write_text(content, encoding="utf-8")
    return True


def ensure_workspace_codex_rules(workspace: Path) -> bool:
    """Create the narrow Brain CLI allow rule when the WoSP lacks one."""
    rules_file = workspace / ".codex" / "rules" / "default.rules"
    if rules_file.exists():
        return False
    rules_file.parent.mkdir(parents=True, exist_ok=True)
    rules_file.write_text(WORKSPACE_CODEX_RULES_TEXT, encoding="utf-8")
    return True


def refresh_workspace_logs_database(workspace: Path) -> Path:
    """
    Refresh the workspace logs database and latest-index projection.

    Args:
        workspace (Path): Workspace root.

    Returns:
        Path: Logs database path.
    """
    migrate_log_files_to_database(workspace_root=workspace, archive_sources=False)
    return get_logs_database_path(workspace_root=workspace)


def create_workspace_brain_entrypoint(workspace: Path, scripts_dir: Path) -> BrainEntrypointResult:
    """
    Clone the relocatable `core/core_cli.py` template as `$agent/scripts/brain.py`.

    Args:
        workspace (Path): Workspace root.
        scripts_dir (Path): Workspace scripts directory.

    Returns:
        BrainEntrypointResult: Created entrypoint metadata.
    """
    template_path: Path = resolve_core_template_path()
    content: str = template_path.read_text(encoding="utf-8")
    workspace_root_text: str = workspace.as_posix()
    relative_core_root: str = Path(
        os.path.relpath(get_core_root(), start=scripts_dir),
    ).as_posix()
    content = re.sub(
        r"^CORE_ROOT\s*=.*$",
        f'CORE_ROOT = (HOME_ROOT / Path("{relative_core_root}")).resolve()',
        content,
        flags=re.MULTILINE,
    )
    destination: Path = scripts_dir / "brain.py"
    destination.write_text(content, encoding="utf-8")
    return BrainEntrypointResult(destination=destination, workspace_root_text=workspace_root_text)


def resolve_core_template_path() -> Path:
    """
    Resolve the canonical `core/core_cli.py` consumer factory.

    Returns:
        Path: Existing `core_cli.py` template path.
    """
    template_path: Path = get_core_cli_path()
    if template_path.is_file():
        return template_path
    raise FileNotFoundError(f"consumer factory not found: {template_path}")
