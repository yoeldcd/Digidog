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
    Return the explicitly configured consumer workspace root.

    Args:
        workspace_root: Optional explicit workspace root.

    Returns:
        Path: Resolved workspace root.

    Raises:
        RuntimeError: Neither an explicit root nor WORKSPACE_ROOT is available.
    """
    if workspace_root is not None:
        return workspace_root.resolve()

    configured_root = os.environ.get("WORKSPACE_ROOT", "").strip()
    if not configured_root:
        raise RuntimeError(
            "Brain requires an explicit workspace_root or configured WORKSPACE_ROOT. "
            "Run commands through the consumer $agent/scripts/brain.py facade."
        )

    return Path(configured_root).resolve()


def get_transient_dir(workspace_root: Path | None = None, core_root: Path | None = None) -> Path:
    """Return the existing patch-owned directory below the transient base.

    The configured ``transient_dir`` is treated as a base directory. When it is
    absent or invalid, the consumer-local ``$agent/.tmp`` directory becomes the
    base. Patch rollback artifacts are confined to the ``patches_rollback``
    child in either case.

    Args:
        workspace_root: Optional consumer workspace root override.
        core_root: Optional Core root override used to locate configuration.

    Returns:
        Path: Existing ``patches_rollback`` directory below the resolved base.
    """
    configured_base = _read_configured_transient_base(core_root=core_root)
    if configured_base is None:
        configured_base = get_workspace_root(workspace_root=workspace_root) / "$agent" / ".tmp"
        configured_base.mkdir(parents=True, exist_ok=True)

    patch_transient_dir = configured_base / "patches_rollback"
    patch_transient_dir.mkdir(parents=True, exist_ok=True)

    return patch_transient_dir


def _read_configured_transient_base(core_root: Path | None = None) -> Path | None:
    """Return a valid absolute configured transient base, when available."""
    config_path = get_core_root(core_root=core_root) / CONFIGS_DIR_NAME / BRAIN_CONFIGS_FILE_NAME
    if not config_path.is_file():
        return None

    try:
        raw_data: object = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    configured_value = raw_data.get("transient_dir") if isinstance(raw_data, dict) else None
    if not isinstance(configured_value, str) or not configured_value.strip():
        return None

    candidate = Path(configured_value.strip()).expanduser()
    if not candidate.is_absolute():
        return None

    resolved_candidate = candidate.resolve()
    if not resolved_candidate.exists() or not resolved_candidate.is_dir():
        return None

    return resolved_candidate


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
    """Create and return one non-private core directory.

    Args:
        path (Path): Directory to create.

    Returns:
        Path: Created directory path.
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_configs_dir(core_root: Path | None = None, create: bool = True) -> Path:
    """Return the core-owned configuration directory.

    Args:
        core_root (Path | None): Optional core-root override.
        create (bool): Whether to create the directory.

    Returns:
        Path: Core configuration directory.
    """
    configs_dir: Path = get_core_root(core_root=core_root) / CONFIGS_DIR_NAME
    return ensure_directory(path=configs_dir) if create else configs_dir


def get_core_database_dir(core_root: Path | None = None, create: bool = True) -> Path:
    """Return the container for all core-owned database families.

    Args:
        core_root (Path | None): Optional core-root override.
        create (bool): Whether to create the directory.

    Returns:
        Path: Core database directory.
    """
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
        scope (str): Runtime scope: `global` or `local`.
        agent_home (Path | None): Optional shared agent home.
        workspace_root (Path | None): Optional workspace root.
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
    """Return the core-owned consumer workspace registry path.

    Returns:
        Path: Canonical Brain mirrors registry path.
    """
    return get_configs_dir() / BRAIN_MIRRORS_FILE_NAME


def get_avatar_config_path() -> Path:
    """Return the core-owned avatar and voice configuration path.

    Returns:
        Path: Canonical avatar configuration file.
    """
    return get_configs_dir() / BRAIN_AVATAR_CONFIG_FILE_NAME


def get_avatar_storage_dir(create: bool = True) -> Path:
    """Return the core-owned retained avatar runtime directory.

    Args:
        create (bool): Whether to create the directory.

    Returns:
        Path: Avatar runtime storage directory.
    """
    path: Path = get_core_database_dir(create=create) / AVATAR_STORAGE_DIR_NAME
    return ensure_private_directory(path=path) if create else path


def get_picture_storage_dir(create: bool = True) -> Path:
    """Return the core-owned private picture registry directory.

    Args:
        create (bool): Whether to create the directory.

    Returns:
        Path: Picture registry storage directory.
    """
    path: Path = get_core_database_dir(create=create) / PICTURE_STORAGE_DIR_NAME
    return ensure_private_directory(path=path) if create else path


def get_picture_database_path(create: bool = True) -> Path:
    """Return the SQLite database used by the picture registry.

    Args:
        create (bool): Whether to create the parent directory.

    Returns:
        Path: Picture registry database path.
    """
    return get_picture_storage_dir(create=create) / PICTURE_STORAGE_DB_NAME


def get_pictures_dir(agent_home: Path | None = None, create: bool = True) -> Path:
    """Return the agent-owned image library root.

    Args:
        agent_home (Path | None): Optional agent-home override.
        create (bool): Whether to create the directory.

    Returns:
        Path: Agent picture library root.
    """
    path: Path = get_agent_home(agent_home=agent_home) / PICTURES_DIR_NAME
    return ensure_directory(path=path) if create else path


def normalize_picture_scope(scope: str) -> str:
    """Normalize and validate the picture registry scope.

    Args:
        scope (str): Requested picture source scope.

    Returns:
        str: Canonical lower-case scope.

    Raises:
        ValueError: If the scope is not local or global.
    """
    normalized_scope = str(scope).casefold().strip()
    if normalized_scope not in {"local", "global"}:
        raise ValueError(f"Unsupported picture scope {scope}. Use local or global.")
    return normalized_scope


def get_picture_root(
    scope: str,
    agent_home: Path | None = None,
    core_root: Path | None = None,
    create: bool = True,
) -> Path:
    """Return the filesystem root for one picture registry scope.

    Local registrations are rooted below $agent/pictures/images while global
    registrations are rooted below the core pictures directory.

    Args:
        scope (str): local or global.
        agent_home (Path | None): Optional agent-home override for local data.
        core_root (Path | None): Optional core-root override for global data.
        create (bool): Whether to create the selected directory.

    Returns:
        Path: Resolved scope root.
    """
    normalized_scope = normalize_picture_scope(scope)
    if normalized_scope == "local":
        path = get_pictures_dir(agent_home=agent_home) / "images"
    else:
        path = get_core_root(core_root=core_root) / PICTURES_DIR_NAME
    return ensure_directory(path=path) if create else path


def resolve_picture_path(scope: str, relative_path: str, create: bool = False) -> Path:
    """Resolve a registered picture path without allowing scope escape.

    Local records may be legacy files below ``$agent/pictures`` or canonical
    registrations below ``$agent/pictures/images``; global records resolve
    below the core picture root.
    """
    normalized_scope = normalize_picture_scope(scope)
    normalized_relative = Path(str(relative_path).replace(chr(92), "/")).as_posix()
    if not normalized_relative or normalized_relative in {".", ".."} or Path(normalized_relative).is_absolute():
        raise ValueError("Picture relative path is invalid.")
    roots = [get_picture_root(scope=normalized_scope, create=create)]
    if normalized_scope == "local":
        roots.append(get_pictures_dir(create=create))
    for root in roots:
        candidate = (root / normalized_relative).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError("Registered picture path escapes its scope root.") from exc
        if candidate.is_file():
            return candidate
    candidate = (roots[0] / normalized_relative).resolve()
    candidate.relative_to(roots[0].resolve())
    return candidate


def get_avatar_assets_dir(create: bool = False) -> Path:
    """Return the core-owned avatar state asset directory.

    Args:
        create (bool): Whether to create the directory.

    Returns:
        Path: Avatar state asset directory.
    """
    path: Path = get_core_root() / ASSETS_DIR_NAME / AVATAR_ASSETS_DIR_NAME
    return ensure_directory(path=path) if create else path


def get_brain_explorer_dist_dir() -> Path:
    """Return the generated Brain Explorer distribution directory.

    Returns:
        Path: Explorer frontend distribution directory.
    """
    return get_core_root() / "brain_explorer" / "dist"


def get_core_cli_path() -> Path:
    """Return the canonical consumer-factory entrypoint.

    Returns:
        Path: Core CLI factory script.
    """
    return get_core_root() / "core_cli.py"


def get_utilities_dir() -> Path:
    """Return the core-owned reusable utilities directory.

    Returns:
        Path: Shared utilities directory.
    """
    return get_core_root() / "utilities"


def get_documentation_utility_cli_path() -> Path:
    """Return the canonical documentation utility CLI entrypoint.

    Returns:
        Path: Documentation utility script.
    """
    return get_utilities_dir() / "documentation_utils" / "documentation_cli.js"


def get_prompt_propagator_path() -> Path:
    """Return the canonical agent-prompt propagator entrypoint.

    Returns:
        Path: Prompt propagation script.
    """
    return get_utilities_dir() / "propagate_agent_prompt" / "propagate_agent_prompt.py"


def get_instruction_mirrors_registry_path(create: bool = True) -> Path:
    """Return the registry of canonical prompt mirror destinations.

    Args:
        create (bool): Whether to create the parent directory.

    Returns:
        Path: Instruction mirror registry path.
    """
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

    Raises:
        ValueError: The scope is neither global nor local.
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
        scope (str): Runtime scope: `global` or `local`.
        agent_home (Path | None): Optional shared agent home.
        workspace_root (Path | None): Optional workspace root.

    Returns:
        Path: Scoped source registry database path.

    Raises:
        ValueError: The scope is neither global nor local.
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
        scope (str): Runtime scope: `global` or `local`.
        agent_home (Path | None): Optional shared agent home.
        workspace_root (Path | None): Optional workspace root.
        create (bool): Whether to create the private vectorstore directory.

    Returns:
        Path: Scoped vectorstore directory.

    Raises:
        ValueError: The scope is neither global nor local.
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
    """Return the core-owned global logs database directory.

    Args:
        create (bool): Whether to create the directory.

    Returns:
        Path: Global logs database directory.
    """
    path: Path = get_core_database_dir(create=create) / GLOBAL_LOGS_DIR_NAME
    return ensure_private_directory(path=path) if create else path


def register_project_path(project_path: Path) -> None:
    """Register a local project workspace in the Brain mirrors registry.

    Args:
        project_path (Path): Workspace root to register.
    """
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
