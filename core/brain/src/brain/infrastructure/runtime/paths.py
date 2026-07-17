# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Filesystem path resolution for private brain runtime stores."""

from __future__ import annotations

# Standard Libraries Imports
import json
import os
from pathlib import Path

# Application Modules Imports
from brain.config import (
    ASSETS_DIR_NAME,
    AVATAR_ASSETS_DIR_NAME,
    AVATAR_STORAGE_DIR_NAME,
    BRAIN_AVATAR_CONFIG_FILE_NAME,
    BRAIN_CONFIGS_FILE_NAME,
    BRAIN_KNOWLEDGE_DB_NAME,
    BRAIN_MIRRORS_FILE_NAME,
    BRAIN_SOURCES_DB_NAME,
    BRAIN_VECTORSTORE_DIR_NAME,
    CONFIGS_DIR_NAME,
    DATABASE_DIR_NAME,
    DATABASE_GITIGNORE_TEXT,
    DEFAULT_WORKSPACE_ROOT,
    GLOBAL_KNOWLEDGE_DIR_NAME,
    GLOBAL_LOGS_DIR_NAME,
    GLOBAL_SOURCES_DIR_NAME,
    GLOBAL_VECTORSTORES_DIR_NAME,
    INSTRUCTION_MIRRORS_DIR_NAME,
    INSTRUCTION_MIRRORS_FILE_NAME,
    LOCAL_SOURCES_DB_NAME,
    PICTURE_STORAGE_DB_NAME,
    PICTURE_STORAGE_DIR_NAME,
    PICTURES_DIR_NAME,
)


def get_core_root(core_root: Path | None = None) -> Path:
    """
    Return the canonical core root without relying on a machine-specific path.

    Args:
        core_root: Optional explicit core root.

    Returns:
        Path: Resolved directory containing Brain, Explorer, configs, databases,
        assets, and utilities.
    """
    if core_root is not None:
        return core_root.resolve()
    return Path(__file__).resolve().parents[5]


def get_agent_home(agent_home: Path | None = None) -> Path:
    """
    Return the shared agent home path.

    Args:
        agent_home: Optional explicit agent home.

    Returns:
        Path: Resolved shared agent home.
    """
    if agent_home is not None:
        return agent_home.resolve()
    configured_path: Path | None = _read_configured_agent_home()
    if configured_path is not None:
        return configured_path
    return get_core_root().parent


def _read_configured_agent_home() -> Path | None:
    """Read the canonical agent directory from the core configuration."""
    config_path: Path = get_core_root() / CONFIGS_DIR_NAME / BRAIN_CONFIGS_FILE_NAME
    if not config_path.is_file():
        return None
    try:
        raw_data: object = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw_data, dict):
        return None
    configured_value: object = raw_data.get("agent_dir")
    if not isinstance(configured_value, str) or not configured_value.strip():
        return None
    configured_path: Path = Path(configured_value).expanduser()
    if not configured_path.is_absolute():
        configured_path = get_core_root() / configured_path
    return configured_path.resolve()


def get_workspace_root(workspace_root: Path | None = None) -> Path:
    """
    Return the current workspace root path.

    Args:
        workspace_root: Optional explicit workspace root.

    Returns:
        Path: Resolved workspace root.
    """
    return (workspace_root or Path(os.environ.get("WORKSPACE_ROOT", DEFAULT_WORKSPACE_ROOT))).resolve()


def ensure_private_directory(path: Path) -> Path:
    """
    Create one private runtime directory and its internal gitignore.

    Args:
        path: Directory path to create.

    Returns:
        Path: Created directory path.
    """
    path.mkdir(parents=True, exist_ok=True)
    gitignore_path: Path = path / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(DATABASE_GITIGNORE_TEXT, encoding="utf-8")
    return path


def ensure_directory(path: Path) -> Path:
    """Create and return one non-private core directory."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_configs_dir(core_root: Path | None = None, create: bool = True) -> Path:
    """Return the core-owned configuration directory."""
    configs_dir: Path = get_core_root(core_root=core_root) / CONFIGS_DIR_NAME
    return ensure_directory(path=configs_dir) if create else configs_dir


def get_core_database_dir(core_root: Path | None = None, create: bool = True) -> Path:
    """Return the container for all core-owned database families."""
    database_dir: Path = get_core_root(core_root=core_root) / DATABASE_DIR_NAME
    return ensure_private_directory(path=database_dir) if create else database_dir


def get_global_database_dir(agent_home: Path | None = None, create: bool = True) -> Path:
    """
    Return the shared global database directory.

    Args:
        agent_home: Retained compatibility argument; core data never derives
            from the agent directory.
        create: Whether to create the directory.

    Returns:
        Path: Global database directory.
    """
    del agent_home
    database_dir: Path = get_core_database_dir(create=create) / GLOBAL_KNOWLEDGE_DIR_NAME
    return ensure_private_directory(path=database_dir) if create else database_dir


def get_local_database_dir(workspace_root: Path | None = None, create: bool = True) -> Path:
    """
    Return the workspace-local database directory.

    Args:
        workspace_root: Optional workspace root.
        create: Whether to create the directory.

    Returns:
        Path: Local database directory.
    """
    database_dir: Path = get_workspace_root(workspace_root=workspace_root) / "$agent" / DATABASE_DIR_NAME
    return ensure_private_directory(path=database_dir) if create else database_dir


def get_database_dir(
    scope: str,
    agent_home: Path | None = None,
    workspace_root: Path | None = None,
    create: bool = True,
) -> Path:
    """
    Return a database directory by scope.

    Args:
        scope: Runtime scope: `global` or `local`.
        agent_home: Optional shared agent home.
        workspace_root: Optional workspace root.
        create: Whether to create the directory.

    Returns:
        Path: Scoped database directory.

    Raises:
        ValueError: If the scope is unsupported.
    """
    normalized_scope: str = scope.casefold().strip()
    if normalized_scope == "global":
        return get_global_database_dir(agent_home=agent_home, create=create)
    if normalized_scope == "local":
        return get_local_database_dir(workspace_root=workspace_root, create=create)
    raise ValueError(f"Unsupported database scope `{scope}`. Use global or local.")


def get_brain_configs_path(agent_home: Path | None = None) -> Path:
    """
    Return the unified global brain config path.

    Args:
        agent_home: Retained compatibility argument; core config never derives
            from the agent directory.

    Returns:
        Path: `brain_configs.json` path.
    """
    del agent_home
    return get_configs_dir() / BRAIN_CONFIGS_FILE_NAME


def get_brain_mirrors_path() -> Path:
    """Return the core-owned consumer workspace registry path."""
    return get_configs_dir() / BRAIN_MIRRORS_FILE_NAME


def get_avatar_config_path() -> Path:
    """Return the core-owned avatar and voice configuration path."""
    return get_configs_dir() / BRAIN_AVATAR_CONFIG_FILE_NAME


def get_avatar_storage_dir(create: bool = True) -> Path:
    """Return the core-owned retained avatar runtime directory."""
    path: Path = get_core_database_dir(create=create) / AVATAR_STORAGE_DIR_NAME
    return ensure_private_directory(path=path) if create else path


def get_picture_storage_dir(create: bool = True) -> Path:
    """Return the core-owned private picture registry directory."""
    path: Path = get_core_database_dir(create=create) / PICTURE_STORAGE_DIR_NAME
    return ensure_private_directory(path=path) if create else path


def get_picture_database_path(create: bool = True) -> Path:
    """Return the SQLite database used by the picture registry."""
    return get_picture_storage_dir(create=create) / PICTURE_STORAGE_DB_NAME


def get_pictures_dir(agent_home: Path | None = None, create: bool = True) -> Path:
    """Return the agent-owned image library root."""
    path: Path = get_agent_home(agent_home=agent_home) / PICTURES_DIR_NAME
    return ensure_directory(path=path) if create else path


def get_avatar_assets_dir(create: bool = False) -> Path:
    """Return the core-owned avatar state asset directory."""
    path: Path = get_core_root() / ASSETS_DIR_NAME / AVATAR_ASSETS_DIR_NAME
    return ensure_directory(path=path) if create else path


def get_brain_explorer_dist_dir() -> Path:
    """Return the generated Brain Explorer distribution directory."""
    return get_core_root() / "brain_explorer" / "dist"


def get_core_cli_path() -> Path:
    """Return the canonical consumer-factory entrypoint."""
    return get_core_root() / "core_cli.py"


def get_utilities_dir() -> Path:
    """Return the core-owned reusable utilities directory."""
    return get_core_root() / "utilities"


def get_documentation_utility_cli_path() -> Path:
    """Return the canonical Documentation Utils CLI entrypoint."""
    return get_utilities_dir() / "documentation_utils" / "documentation_cli.js"


def get_prompt_propagator_path() -> Path:
    """Return the canonical agent-prompt propagator entrypoint."""
    return get_utilities_dir() / "propagate_agent_prompt" / "propagate_agent_prompt.py"


def get_instruction_mirrors_registry_path(create: bool = True) -> Path:
    """Return the core-owned registry of canonical prompt mirror destinations."""
    directory: Path = get_core_database_dir(create=create) / INSTRUCTION_MIRRORS_DIR_NAME
    if create:
        directory = ensure_private_directory(path=directory)
    return directory / INSTRUCTION_MIRRORS_FILE_NAME


def get_knowledge_database_path(
    scope: str,
    agent_home: Path | None = None,
    workspace_root: Path | None = None,
) -> Path:
    """
    Return the scoped knowledge graph database path.

    Args:
        scope: Runtime scope: `global` or `local`.
        agent_home: Optional shared agent home.
        workspace_root: Optional workspace root.

    Returns:
        Path: Scoped knowledge graph database path.
    """
    normalized_scope: str = scope.casefold().strip()
    if normalized_scope == "global":
        return get_global_database_dir(agent_home=agent_home) / BRAIN_KNOWLEDGE_DB_NAME
    if normalized_scope == "local":
        return get_local_database_dir(workspace_root=workspace_root) / LOCAL_SOURCES_DB_NAME
    raise ValueError(f"Unsupported knowledge database scope `{scope}`. Use global or local.")


def get_source_registry_path(
    scope: str,
    agent_home: Path | None = None,
    workspace_root: Path | None = None,
) -> Path:
    """
    Return the scoped source registry database path.

    Args:
        scope: Runtime scope: `global` or `local`.
        agent_home: Optional shared agent home.
        workspace_root: Optional workspace root.

    Returns:
        Path: Scoped source registry database path.
    """
    normalized_scope: str = scope.casefold().strip()
    if normalized_scope == "global":
        del agent_home
        sources_dir: Path = get_core_database_dir() / GLOBAL_SOURCES_DIR_NAME
        return ensure_private_directory(path=sources_dir) / BRAIN_SOURCES_DB_NAME
    if normalized_scope == "local":
        return get_local_database_dir(workspace_root=workspace_root) / BRAIN_SOURCES_DB_NAME
    raise ValueError(f"Unsupported database scope `{scope}`. Use global or local.")


def get_vectorstore_dir(
    scope: str,
    agent_home: Path | None = None,
    workspace_root: Path | None = None,
    create: bool = True,
) -> Path:
    """
    Return the scoped vectorstore directory.

    Args:
        scope: Runtime scope: `global` or `local`.
        agent_home: Optional shared agent home.
        workspace_root: Optional workspace root.
        create: Whether to create the private vectorstore directory.

    Returns:
        Path: Scoped vectorstore directory.
    """
    normalized_scope: str = scope.casefold().strip()
    if normalized_scope == "global":
        del agent_home
        vectorstore_dir: Path = get_core_database_dir(create=create) / GLOBAL_VECTORSTORES_DIR_NAME
        return ensure_private_directory(path=vectorstore_dir) if create else vectorstore_dir
    if normalized_scope == "local":
        return get_local_database_dir(workspace_root=workspace_root, create=create) / BRAIN_VECTORSTORE_DIR_NAME
    raise ValueError(f"Unsupported database scope `{scope}`. Use global or local.")


def get_global_logs_database_dir(create: bool = True) -> Path:
    """Return the core-owned global logs database directory."""
    path: Path = get_core_database_dir(create=create) / GLOBAL_LOGS_DIR_NAME
    return ensure_private_directory(path=path) if create else path


def register_project_path(project_path: Path) -> None:
    """Register a local project workspace path to the brain mirrors JSON list."""
    import json
    mirrors_file: Path = get_brain_mirrors_path()

    projects = []
    if mirrors_file.is_file():
        try:
            data = json.loads(mirrors_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                projects = data
        except Exception:
            pass

    resolved_path = str(project_path.resolve().as_posix())
    project_name = project_path.resolve().name

    # Check if already registered
    exists = False
    for proj in projects:
        if proj.get("path") == resolved_path:
            exists = True
            break

    if not exists:
        projects.append({
            "name": project_name,
            "path": resolved_path
        })
        mirrors_file.write_text(json.dumps(projects, ensure_ascii=False, indent=2), encoding="utf-8")
