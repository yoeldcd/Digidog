"""Provide runtime adapters for agent-directory lifecycle use cases.

The module keeps path resolution, template composition, staging, publication, and
lifecycle command execution behind small, behavior-preserving helpers.
"""

from __future__ import annotations

import hashlib
import json
import shutil

import uuid
from pathlib import Path
from typing import Callable, Mapping

from .lifecycle_runner import run_lifecycle
from .operation_executor import FilesystemOperationExecutor
from .renderer import render_template
from .resource_loader import ResourceLoader


def resolve_source_root(invoked_file: Path) -> Path:
    """Resolve the source agent root from an invoked script path.

    Args:
        invoked_file: Path to the script or directory used to invoke the runtime.

    Returns:
        Path: Resolved source agent root.
    """
    path = invoked_file.resolve()

    for ancestor in (path, *path.parents):
        core_directory = ancestor / "core"
        if core_directory.is_dir():
            return ancestor

    raise ValueError("invoked path is unrelated to an agent root")


def resolve_target_root(agent_or_core: Path) -> Path:
    """Resolve an agent root when given either its root or its core directory.

    Args:
        agent_or_core: Agent root or core directory path.

    Returns:
        Path: Resolved agent root.
    """
    path = agent_or_core.resolve()

    if path.name == "core":
        return path.parent

    return path


def read_target_identity(target_root: Path) -> tuple[str, str]:
    """Read agent and user names from target brain configuration.

    Args:
        target_root: Root directory containing the brain configuration.

    Returns:
        tuple[str, str]: Agent name followed by user name.

    Raises:
        FileNotFoundError: If the brain configuration does not exist.
        json.JSONDecodeError: If the configuration is not valid JSON.
        KeyError: If required identity keys are absent.
    """
    config_path = target_root / "core" / "configs" / "brain_configs.json"
    config_data = json.loads(config_path.read_text(encoding="utf-8"))

    return str(config_data["agent_name"]), str(config_data["user_name"])


def stable_voice_port(agent_root: Path) -> int:
    """Derive a stable unprivileged voice port from an agent path.

    Args:
        agent_root: Root directory whose path determines the port.

    Returns:
        int: Stable port in the range 10,000 through 59,999.
    """
    digest = hashlib.sha256(agent_root.resolve().as_posix().encode("utf-8")).digest()
    path_value = int.from_bytes(digest[:8], "big")

    return 18000 + path_value % 20000


def build_render_values(agent_root: Path, agent_name: str, user_name: str) -> Mapping[str, object]:
    """Build complete placeholder values for all bundled templates.

    Args:
        agent_root: Root directory used by rendered templates.
        agent_name: Name assigned to the agent.
        user_name: Name assigned to the user.

    Returns:
        Mapping[str, object]: Placeholder names and their injected values.
    """
    root = agent_root.resolve()

    return {
        "AGENT_NAME": agent_name,
        "USER_NAME": user_name,
        "AGENT_DIR": str(root),
        "TRANSIENT_DIR": str(root / ".tmp"),
        "MODEL": "disabled",
        "BASE_URL": "https://provider.example",
        "API_KEY_REF": "${PROVIDER_API_KEY}",
        "EMBEDDING_MODEL": "disabled",
        "VISION_MODEL": "disabled",
        "DEFAULT_LANGUAGE": "en",
        "VOICE_HOST": "127.0.0.1",
        "VOICE_PORT": stable_voice_port(root),
        "TTS_MODEL": "default",
        "TTS_VOICE": "default",
        "ELEVEN_MODEL": "eleven_multilingual_v2",
        "VOICE_ID": "default",
        "MIRROR_NAME": agent_name,
        "MIRROR_PATH": str(root),
    }


def build_resource_renderer(
    loader: ResourceLoader,
    values: Mapping[str, object],
) -> Callable[[str], str]:
    """Create a renderer that loads templates and applies injected values.

    Args:
        loader: Resource loader used to read template text.
        values: Placeholder values passed to the renderer.

    Returns:
        Callable[[str], str]: Renderer accepting a relative template path.

    Raises:
        KeyError: Propagated when a template references a missing placeholder.
    """

    def render(relative_path: str) -> str:
        """Render one template using the bound loader and values.

        Args:
            relative_path: Relative path to the template resource.

        Returns:
            str: Rendered template content.
        """
        template_text = loader.read_text(relative_path)

        return render_template(template_text, values)

    return render


def build_executor_factory(
    source_root: Path,
) -> Callable[[Path, Path, Mapping[str, object]], FilesystemOperationExecutor]:
    """Create an operation-executor factory bound to source resources.

    Args:
        source_root: Root directory containing source resources.

    Returns:
        Callable[[Path, Path, Mapping[str, object]], FilesystemOperationExecutor]:
            Factory accepting source, target, and render values.

    Raises:
        OSError: Propagated when source resources cannot be loaded.
    """

    def factory(
        source: Path,
        target: Path,
        values: Mapping[str, object],
    ) -> FilesystemOperationExecutor:
        """Build one filesystem operation executor.

        Args:
            source: Source resource directory.
            target: Target agent directory.
            values: Placeholder values for rendered resources.

        Returns:
            FilesystemOperationExecutor: Configured operation executor.
        """
        bound_source = source_root.resolve()
        loader = ResourceLoader(bound_source / source)
        renderer = build_resource_renderer(loader, values)

        return FilesystemOperationExecutor(source, target, renderer)

    return factory


def path_exists(path: Path) -> bool:
    """Return whether a destination or staging path exists.

    Args:
        path: Path to inspect.

    Returns:
        bool: Whether the path exists.
    """
    return path.exists()


def sibling_staging_path(agent_root: Path) -> Path:
    """Return a collision-resistant sibling staging directory path.

    Args:
        agent_root: Agent root beside which staging should be created.

    Returns:
        Path: Unique sibling staging path.
    """
    staging_name = f".{agent_root.name}.staging-{uuid.uuid4().hex}"

    return agent_root.with_name(staging_name)


def publish_staging(staging_root: Path, destination: Path) -> None:
    """Atomically publish staging without replacing an existing destination.

    Args:
        staging_root: Staging directory to publish.
        destination: Destination path that must not already exist.

    Raises:
        FileExistsError: If the destination already exists.
        OSError: If publication fails.
    """
    if destination.exists():
        raise FileExistsError(destination)

    staging_root.replace(destination)


def rollback_staging(staging_root: Path) -> None:
    """Remove staging content only when it remains within its parent.

    Args:
        staging_root: Staging directory to remove.

    Raises:
        ValueError: If the staging path resolves outside its parent.
        OSError: If staging removal fails.
    """
    if not staging_root.exists():
        return

    resolved_staging = staging_root.resolve()
    resolved_parent = staging_root.parent.resolve()
    resolved_staging.relative_to(resolved_parent)
    if not resolved_staging.name.startswith(f".{resolved_parent.name}.staging-"):
        raise ValueError("unexpected staging path")
    shutil.rmtree(resolved_staging)


def create_lifecycle(staging_root: Path) -> None:
    """Bootstrap an agent through the core CLI without capturing output.

    Args:
        staging_root: Staging root passed to the create-brain command.

    Raises:
        subprocess.CalledProcessError: If the lifecycle command fails.
        OSError: If the command cannot be started.
    """
    command = (
        "py",
        str(staging_root / "core" / "core_cli.py"),
        "create-brain",
        str(staging_root),
    )
    run_lifecycle(command)


def update_lifecycle(target_root: Path) -> None:
    """Initialize an existing agent through its $agent/scripts/brain.py launcher.

    Args:
        target_root: Existing agent root containing $agent/scripts/brain.py.

    Raises:
        subprocess.CalledProcessError: If the lifecycle command fails.
        OSError: If the command cannot be started.
    """
    command = (
        "py",
        str(target_root / "$agent" / "scripts" / "brain.py"),
        "init",
        "--json",
    )
    run_lifecycle(command, cwd=target_root)
