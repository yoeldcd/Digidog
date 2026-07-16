# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Knowledge graph scope normalization and runtime-root selection."""

from __future__ import annotations

# Standard Libraries Imports
from pathlib import Path

# Application Modules Imports
from brain.config import KNOWLEDGE_SCOPES, KNOWLEDGE_SCOPE_VALUES
from brain.infrastructure.runtime.paths import get_brain_configs_path, get_database_dir


def normalize_knowledge_scope(scope: str, allow_all: bool = False) -> str:
    """
    Normalize a knowledge scope selector.

    Args:
        scope: Raw scope selector.
        allow_all: Whether `all` is accepted.

    Returns:
        str: Normalized scope value.

    Raises:
        ValueError: If the scope is unsupported.
    """
    normalized_scope: str = scope.casefold().strip()
    valid_values: tuple[str, ...] = KNOWLEDGE_SCOPE_VALUES if allow_all else KNOWLEDGE_SCOPES
    if normalized_scope not in valid_values:
        allowed_text: str = ", ".join(valid_values)
        raise ValueError(f"Unsupported knowledge scope `{scope}`. Use one of: {allowed_text}.")
    return normalized_scope


def get_knowledge_root(
    agent_home: Path | None = None,
    scope: str = "global",
    workspace_root: Path | None = None,
) -> Path:
    """
    Return the private database directory that stores knowledge runtime files.

    Args:
        agent_home: Optional agent home override.
        scope: Physical knowledge scope: `global` or `local`.
        workspace_root: Optional workspace root override for local scope.

    Returns:
        Path: Scoped private database directory.
    """
    normalized_scope: str = normalize_knowledge_scope(scope=scope)
    return get_database_dir(
        scope=normalized_scope,
        agent_home=agent_home,
        workspace_root=workspace_root,
    )


def get_shared_config_root(agent_home: Path | None = None) -> Path:
    """
    Return the core configs root that owns the shared config file.

    Args:
        agent_home: Optional agent home override.

    Returns:
        Path: Core configuration root.
    """
    return get_brain_configs_path(agent_home=agent_home).parent


def iter_knowledge_roots(
    scope: str = "global",
    agent_home: Path | None = None,
    workspace_root: Path | None = None,
) -> list[tuple[str, Path]]:
    """
    Return selected knowledge runtime roots.

    Args:
        scope: Scope selector: `global`, `local`, or `all`.
        agent_home: Optional agent home override.
        workspace_root: Optional workspace root override.

    Returns:
        list[tuple[str, Path]]: Scope names paired with runtime roots.
    """
    normalized_scope: str = normalize_knowledge_scope(scope=scope, allow_all=True)
    if normalized_scope != "all":
        return [
            (
                normalized_scope,
                get_knowledge_root(
                    agent_home=agent_home,
                    scope=normalized_scope,
                    workspace_root=workspace_root,
                ),
            ),
        ]
    return [
        (
            scope_name,
            get_knowledge_root(
                agent_home=agent_home,
                scope=scope_name,
                workspace_root=workspace_root,
            ),
        )
        for scope_name in KNOWLEDGE_SCOPES
    ]
