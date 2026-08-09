#!/usr/bin/env python
# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Create a new agent directory from the versioned core seed."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


AGENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
STAGE_NAMES = (
    "entity_detection",
    "relation_extraction",
    "schema_evolution",
    "deduplication",
    "consolidation",
    "profile_synthesis",
)
CORE_OWNED_ROOTS = {"configs", "database", "assets"}
COPY_EXCLUDED_NAMES = {
    ".git",
    ".tmp",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
}
CORE_SEED_EXCLUDED_ROOT_NAMES = {"AGENTS.md"}
"""Canonical identity templates that must be rendered for each clone."""
SYNC_ROOT_NAMES = ("brain", "brain_explorer", "assets/screens")
PUBLIC_PROFILE_ROOT_NAMES = ("memory/profiles/developer", "memory/profiles/worker")
UTILITY_SYNC_FILES = (
    "utilities/create_agent_directory/create_agent_directory.py",
    "utilities/create_agent_directory/documentation/README.md",
    "utilities/create_agent_directory/templates/AGENTS.md",
    "utilities/create_agent_directory/templates/LICENSE",
    "utilities/propagate_agent_prompt/propagate_agent_prompt.py",
    "utilities/propagate_agent_prompt/documentation/README.md",
    "utilities/apply_text_patch/apply_text_patch.ps1",
    "utilities/apply_text_patch/documentation/README.md",
    "utilities/create_agent_directory/tests/test_create_agent_directory.py",
)
REQUIRED_EXISTING_ROOT_NAMES = ("brain", "brain_explorer")
SYNC_AGENT_FILE_NAMES = ("LICENSE", "README.md", "core/AGENTS.md")
AVATAR_STATE_PATTERN = re.compile(r"^avatar_[A-Za-z0-9_-]+\.gif$", re.IGNORECASE)
PUBLICATION_TEMPLATE_ROOT = Path(__file__).with_name("templates")

LICENSE_TEMPLATE = PUBLICATION_TEMPLATE_ROOT / "LICENSE"
GENERIC_AGENT_TEMPLATE = PUBLICATION_TEMPLATE_ROOT / "AGENTS.md"
README_CONTRACT_MARKERS = (
    "Digidog",
    "Brain Explorer",
    "Picture intelligence",
    "img2text",
    "create_agent_directory",
    "GNU Affero General Public License",
)
PUBLIC_SCREEN_NAMES = (
    "explorer_home_page.png",
    "explorer_messages_layout.png",
    "explorer_memory_layout.png",
    "explorer_knowledge_layout.png",
    "explorer_image_layout.png",
    "explorer_profiles_layout.png",
    "explorer_logs_domains_layout.png",
    "explorer_logs_times_layout.png",
    "explorer_backlog_layout.png",
    "explorer_wiki_layout.png",
    "explorer_wiki_page.png",
    "avatar_view.png",
)
PRIVATE_STORE_NAMES = (
    "avatar_storage",
    "knowledge",
    "logs",
    "sources",
    "vectorstores",
)
PRIVATE_STORE_GITIGNORE = "*\n!.gitignore\n"
DATABASE_GITIGNORE = (
    "# Mutable runtime stores are private; settings and registries are versioned.\n"
    "avatar_storage/\n"
    "knowledge/\n"
    "logs/\n"
    "sources/\n"
    "vectorstores/\n"
)
AGENT_ROOT_GITIGNORE = """# Python and tool caches
*.pyc
*.pyo
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
node_modules/

# Agent-authored private state
/memory/
/pictures/
/$workspaces/

# Agent-local temporary artifacts
/.tmp/*
!/.tmp/.gitkeep

# Workspace-local runtime state
/$agent/.tmp/
/$agent/database/
/$agent/logs/

# Generated documentation exports
/core/**/documentation/wiki/
"""
@dataclass(frozen=True)
class AgentDirectoryResult:
    """Paths created by one successful seed operation.

    Attributes:
        agent_name (str): Published agent identifier.
        user_name (str): Collaborator display name.
        agent_root (str): Created agent-root path.
        core_root (str): Created Core path.
        consumer_entrypoint (str): Workspace Brain launcher path.
        license_path (str): Published license path.
        readme_path (str): Published README path.
        configs (list[str]): Created versioned configuration paths.
        stores (list[str]): Created private state-store paths.
    """

    agent_name: str
    user_name: str
    agent_root: str
    core_root: str
    consumer_entrypoint: str
    license_path: str
    readme_path: str
    configs: list[str]
    stores: list[str]


@dataclass(frozen=True)
class UpdateAgentResult:
    """Summary of one content-aware agent code synchronization.

    Attributes:
        agent_root (str): Existing agent-root path.
        source_core (str): Canonical Core source path.
        target_core (str): Updated target Core path.
        updated_roots (list[str]): Synchronized code-root names.
        updated_files (list[str]): Synchronized published root-file names.
        copied_files (int): Number of changed files copied.
        unchanged_files (int): Number of identical files preserved.
        removed_files (int): Number of obsolete synchronized files removed.
        created_directories (int): Number of synchronized directories created.
        removed_directories (int): Number of obsolete directories removed.
    """

    agent_root: str
    source_core: str
    target_core: str
    updated_roots: list[str]
    updated_files: list[str]
    copied_files: int
    unchanged_files: int
    removed_files: int
    created_directories: int
    removed_directories: int


@dataclass
class _SyncStats:
    """Mutable counters shared while synchronizing code trees."""

    copied_files: int = 0
    unchanged_files: int = 0
    removed_files: int = 0
    created_directories: int = 0
    removed_directories: int = 0


def build_parser() -> argparse.ArgumentParser:
    """Build the standalone factory command parser.

    Returns:
        argparse.ArgumentParser: Parser for create-agent and update-agent commands.
    """
    parser = argparse.ArgumentParser(
        description="Create an agent directory or update its cloned Brain codebases.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    create_parser = commands.add_parser(
        "create-agent",
        help="Create @<agent-name> with a cloned Brain core and empty stores.",
    )
    create_parser.add_argument(
        "path",
        help="Parent directory where @<agent-name> will be created.",
    )
    create_parser.add_argument(
        "--agent-name",
        "--agent_name",
        "------agent-name",
        dest="agent_name",
        required=True,
        help="Agent identifier, with or without the leading @.",
    )
    create_parser.add_argument(
        "--user-name",
        "--user_name",
        dest="user_name",
        required=True,
        help="Name of the user who will collaborate with the new agent.",
    )
    create_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON result to stdout.",
    )

    update_parser = commands.add_parser(
        "update-agent",
        help=(
            "Synchronize brain/, brain_explorer/, and canonical root publication files "
            "in an existing agent."
        ),
    )
    update_parser.add_argument(
        "path",
        help="Existing agent root or its core directory.",
    )
    update_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON result to stdout.",
    )
    return parser


def parse_cli_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse factory arguments while preserving legacy create invocation form.

    Args:
        argv (Sequence[str] | None): Explicit arguments, or None to use process
            arguments.

    Returns:
        argparse.Namespace: Parsed factory command and its options.
    """
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] not in {"create-agent", "update-agent"}:
        arguments.insert(0, "create-agent")
    return build_parser().parse_args(arguments)


def normalize_agent_name(value: str) -> str:
    """Normalize a safe agent identifier without a leading at sign.

    Args:
        value (str): Raw agent identifier supplied by a caller.

    Returns:
        str: Validated identifier without its optional leading at sign.

    Raises:
        ValueError: If the identifier violates the supported naming pattern.
    """
    normalized = value.strip().lstrip("@").strip()
    if not normalized or not AGENT_NAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            "agent name must match [A-Za-z0-9][A-Za-z0-9_-]* and may start with @",
        )
    return normalized


def normalize_user_name(value: str) -> str:
    """Normalize a non-empty single-line user display name.

    Args:
        value (str): Raw collaborator display name.

    Returns:
        str: Trimmed valid display name.

    Raises:
        ValueError: If the name is empty or contains line-breaking characters.
    """
    normalized = value.strip()
    if not normalized:
        raise ValueError("user name cannot be empty")
    if any(character in normalized for character in ("\r", "\n", "\x00")):
        raise ValueError("user name must be a single line")
    return normalized


def default_model_config(model: str = "google/gemini-2.5-flash") -> dict[str, object]:
    """Build a provider-neutral runtime model configuration.

    Args:
        model (str): Provider model identifier to configure.

    Returns:
        dict[str, object]: Versionable model configuration mapping.
    """
    return {
        "model": model,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "$OPENROUTER_API_KEY",
        "temperature": 0.1,
        "max_tokens": 6000,
        "enabled": True,
    }


def default_picture_config() -> dict[str, object]:
    """Build disabled provider-neutral picture-intelligence defaults.

    Returns:
        dict[str, object]: Picture guidance, model, and extension configuration.
    """
    return {
        "guidance": {
            "tags": {},
            "characters": {},
        },
        "image_model": {
            "model": "provider/vision-model",
            "base_url": "https://provider.example/v1",
            "api_key": "$VISION_API_KEY",
            "temperature": 0.1,
            "max_tokens": 1200,
            "enabled": False,
        },
        "supported_extensions": [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"],
    }


def default_brain_config(agent_root: Path, agent_name: str, user_name: str) -> dict[str, object]:
    """Build the default Brain configuration for a new agent identity.

    Args:
        agent_root (Path): Destination agent-root directory.
        agent_name (str): Raw agent identifier.
        user_name (str): Raw collaborator display name.

    Returns:
        dict[str, object]: Complete versionable Brain configuration mapping.
    """
    return {
        "version": 1,
        "agent_name": f"@{normalize_agent_name(agent_name)}",
        "user_name": normalize_user_name(user_name),
        "agent_dir": str(agent_root.resolve()),
        "knowledge": {
            "version": 1,
            "minimum_confidence": 0.65,
            "stages": {stage: default_model_config() for stage in STAGE_NAMES},
        },
        "memory": {
            "embedding_model": default_model_config("openai/text-embedding-3-small"),
            "text_model": default_model_config(),
        },
        "pictures": default_picture_config(),
    }


def default_avatar_config(agent_root: Path | None = None) -> dict[str, object]:
    """Build generic local avatar voice defaults without personal identifiers.

    Args:
        agent_root (Path | None): Destination agent root used to derive a stable
            local service port, or None for the default port.

    Returns:
        dict[str, object]: Avatar service and engine configuration mapping.
    """
    service_port = 8133 if agent_root is None else _agent_voice_service_port(agent_root)
    return {
        "service": {"host": "127.0.0.1", "port": service_port},
        "active_voice_engine": "edge",
        "voice_engines": {
            "edge": {
                "rate": "+0%",
                "volume": "+0%",
                "pitch": "+0Hz",
                "sanitization_regex": "_+",
                "voices": {
                    "es": "es-ES-ElviraNeural",
                    "en": "en-US-AriaNeural",
                },
            },
            "pyttsx3": {
                "rate": 150,
                "volume": 1.0,
                "voices": {"es": "spanish", "en": "english"},
            },
        },
    }


def _agent_voice_service_port(agent_root: Path) -> int:
    """Derive a stable high local port for one newly created agent core."""
    normalized = agent_root.resolve().as_posix().casefold().encode("utf-8")
    return 18000 + (int(hashlib.sha256(normalized).hexdigest()[:8], 16) % 20000)


def create_agent_directory(
    parent_path: Path,
    agent_name: str,
    user_name: str,
    *,
    source_core: Path | None = None,
    instruction_template: Path | None = None,
) -> AgentDirectoryResult:
    """Create a complete agent seed without copying live private state.

    Args:
        parent_path (Path): Parent directory that will contain the new agent root.
        agent_name (str): Requested agent identifier.
        user_name (str): Collaborator display name.
        source_core (Path | None): Optional injected canonical Core source.
        instruction_template (Path | None): Optional injected AGENT template.

    Returns:
        AgentDirectoryResult: Paths created for the new agent seed.

    Raises:
        FileExistsError: If the destination agent root already exists.
        RuntimeError: If creation fails and its private staging tree cannot be
            cleaned up.
    """
    safe_agent_name = normalize_agent_name(agent_name)
    safe_user_name = normalize_user_name(user_name)
    parent = parent_path.expanduser().resolve()
    agent_root = parent / f"@{safe_agent_name}"
    if agent_root.exists():
        raise FileExistsError(f"destination already exists: {agent_root}")

    canonical_core = (source_core or Path(__file__).resolve().parents[2]).resolve()
    template = (instruction_template or GENERIC_AGENT_TEMPLATE).resolve()
    _validate_seed_sources(
        canonical_core=canonical_core,
        instruction_template=template,
        license_template=LICENSE_TEMPLATE,
    )

    parent.mkdir(parents=True, exist_ok=True)
    temporary_root = parent / f".{agent_root.name}.creating-{uuid.uuid4().hex}"
    published = False
    try:
        temporary_root.mkdir()
        temporary_agent_root = temporary_root
        _copy_core_seed(canonical_core, temporary_agent_root / "core")
        _write_agent_configuration(
            agent_root=temporary_agent_root,
            final_agent_root=agent_root,
            agent_name=safe_agent_name,
            user_name=safe_user_name,
        )
        _create_empty_core_state(
            temporary_agent_root / "core",
            source_core=canonical_core,
        )
        _create_agent_authored_structure(temporary_agent_root)
        _sync_public_profiles(
            source_agent_root=canonical_core.parent,
            target_agent_root=temporary_agent_root,
        )
        _sync_agent_prompt(
            template=template,
            destination=temporary_agent_root / "core" / "AGENTS.md",
            agent_name=safe_agent_name,
            user_name=safe_user_name,
        )
        _write_publication_files(
            agent_root=temporary_agent_root,
            readme_source=canonical_core / "README.md",
        )
        (temporary_agent_root / ".gitignore").write_text(AGENT_ROOT_GITIGNORE, encoding="utf-8")
        _publish_seed(temporary_agent_root, agent_root)
        published = True
        consumer = _create_agent_consumer(agent_root=agent_root)
    except Exception as exc:
        cleanup_root = agent_root if published else temporary_root
        try:
            _remove_failed_seed(cleanup_root)
        except OSError as cleanup_exc:
            raise RuntimeError(
                f"agent creation failed: {exc}; temporary cleanup also failed: {cleanup_exc}",
            ) from exc
        raise

    return AgentDirectoryResult(
        agent_name=f"@{safe_agent_name}",
        user_name=safe_user_name,
        agent_root=agent_root.as_posix(),
        core_root=(agent_root / "core").as_posix(),
        consumer_entrypoint=consumer.as_posix(),
        license_path=(agent_root / "LICENSE").as_posix(),
        readme_path=(agent_root / "README.md").as_posix(),
        configs=[
            (agent_root / "core" / "configs" / name).as_posix()
            for name in ("brain_configs.json", "brain_avatar_config.json", "brain_mirrors.json")
        ],
        stores=[(agent_root / "core" / "database" / name).as_posix() for name in PRIVATE_STORE_NAMES],
    )


def update_agent(
    agent_path: Path,
    *,
    source_core: Path | None = None,
) -> UpdateAgentResult:
    """Synchronize changed Brain code and canonical publication files.

    The source is always the core containing this utility unless explicitly
    injected by a test. Root README.md and LICENSE are overwriteable;
    Configs, databases, private avatar assets, identity, and all agent-authored
    memory domains remain outside the synchronization boundary. Only the
    explicit public utility-file allowlist is synchronized.
    Versioned Explorer screenshots are synchronized with their README.

    Args:
        agent_path (Path): Existing agent root or its Core directory.
        source_core (Path | None): Optional injected canonical Core source.

    Returns:
        UpdateAgentResult: Counts and paths describing synchronized content.

    Raises:
        ValueError: If the target resolves to the canonical Core itself.
    """
    canonical_core = (source_core or Path(__file__).resolve().parents[2]).resolve()
    agent_root, target_core = _resolve_existing_agent(agent_path)
    if target_core == canonical_core:
        raise ValueError("update-agent cannot synchronize a core onto itself")
    _validate_update_sources(canonical_core, target_core)

    total = _SyncStats()
    for root_name in SYNC_ROOT_NAMES:
        current = _sync_code_tree(
            source=canonical_core / root_name,
            destination=target_core / root_name,
        )
        total.copied_files += current.copied_files
        total.unchanged_files += current.unchanged_files
        total.removed_files += current.removed_files
        total.created_directories += current.created_directories
        total.removed_directories += current.removed_directories

    profiles = _sync_public_profiles(
        source_agent_root=canonical_core.parent,
        target_agent_root=agent_root,
    )
    total.copied_files += profiles.copied_files
    total.unchanged_files += profiles.unchanged_files

    documentation_utils = canonical_core / "utilities/documentation_utils"
    if documentation_utils.is_dir():
        current = _sync_code_tree(
            source=documentation_utils,
            destination=target_core / "utilities/documentation_utils",
        )
        total.copied_files += current.copied_files
        total.unchanged_files += current.unchanged_files
        total.removed_files += current.removed_files
        total.created_directories += current.created_directories
        total.removed_directories += current.removed_directories

    utilities = _sync_allowlisted_utilities(source_core=canonical_core, target_core=target_core)
    total.copied_files += utilities.copied_files
    total.unchanged_files += utilities.unchanged_files

    publication = _sync_publication_files(
        agent_root=agent_root,
        readme_source=canonical_core / "README.md",
    )
    total.copied_files += publication.copied_files
    total.unchanged_files += publication.unchanged_files
    agent_name, user_name = _read_agent_identity(agent_root)
    prompt = _sync_agent_prompt(
        template=canonical_core / "utilities" / "create_agent_directory" / "templates" / "AGENTS.md",
        destination=target_core / "AGENTS.md",
        agent_name=agent_name,
        user_name=user_name,
    )
    total.copied_files += prompt.copied_files
    total.unchanged_files += prompt.unchanged_files
    _initialize_agent_consumer(agent_root)

    return UpdateAgentResult(
        agent_root=agent_root.as_posix(),
        source_core=canonical_core.as_posix(),
        target_core=target_core.as_posix(),
        updated_roots=[*SYNC_ROOT_NAMES, "utilities/documentation_utils", *PUBLIC_PROFILE_ROOT_NAMES, "utilities"],
        updated_files=[*SYNC_AGENT_FILE_NAMES, *UTILITY_SYNC_FILES],
        copied_files=total.copied_files,
        unchanged_files=total.unchanged_files,
        removed_files=total.removed_files,
        created_directories=total.created_directories,
        removed_directories=total.removed_directories,
    )


def _sync_file_by_content(source: Path, destination: Path) -> _SyncStats:
    """Atomically synchronize one allowlisted file by content."""
    stats = _SyncStats()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_dir():
        raise OSError(f"directory blocks synchronized file: {destination}")
    if destination.is_file() and _files_match(source, destination):
        stats.unchanged_files += 1
        return stats

    temporary = destination.with_name(f".{destination.name}.updating-{uuid.uuid4().hex}")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    stats.copied_files += 1
    return stats


def _sync_public_profiles(source_agent_root: Path, target_agent_root: Path) -> _SyncStats:
    """Synchronize only the public developer and worker profile trees."""
    total = _SyncStats()
    for relative_name in PUBLIC_PROFILE_ROOT_NAMES:
        source = source_agent_root / relative_name
        if not source.is_dir():
            continue
        current = _sync_code_tree(source=source, destination=target_agent_root / relative_name)
        total.copied_files += current.copied_files
        total.unchanged_files += current.unchanged_files
        total.removed_files += current.removed_files
        total.created_directories += current.created_directories
        total.removed_directories += current.removed_directories
    return total


def _sync_allowlisted_utilities(source_core: Path, target_core: Path) -> _SyncStats:
    """Synchronize the explicit canonical utility-file allowlist."""
    total = _SyncStats()
    for relative_name in UTILITY_SYNC_FILES:
        source = source_core / relative_name
        if not source.is_file():
            raise FileNotFoundError(f"canonical utility file not found: {source}")
        current = _sync_file_by_content(source, target_core / relative_name)
        total.copied_files += current.copied_files
        total.unchanged_files += current.unchanged_files
    return total


def _resolve_existing_agent(agent_path: Path) -> tuple[Path, Path]:
    """Resolve an existing agent root from either the root or core path."""
    candidate = agent_path.expanduser().resolve()
    candidate_is_core = all((candidate / root_name).is_dir() for root_name in REQUIRED_EXISTING_ROOT_NAMES)
    target_core = candidate if candidate_is_core else candidate / "core"
    agent_root = target_core.parent
    if not agent_root.is_dir() or not target_core.is_dir():
        raise FileNotFoundError(f"existing agent core not found: {target_core}")
    return agent_root, target_core


def _validate_update_sources(source_core: Path, target_core: Path) -> None:
    """Validate source roots while allowing update to introduce new destination roots."""
    required_directories = (
        *((source_core / root_name) for root_name in SYNC_ROOT_NAMES),
        *((target_core / root_name) for root_name in REQUIRED_EXISTING_ROOT_NAMES),
    )
    missing = [path.as_posix() for path in required_directories if not path.is_dir()]
    required_files = (
        source_core / "README.md",
        *(source_core / relative_name for relative_name in UTILITY_SYNC_FILES),
    )
    missing.extend(path.as_posix() for path in required_files if not path.is_file())
    if missing:
        raise FileNotFoundError(f"incomplete update boundary; missing: {', '.join(missing)}")
    _validate_readme_contract(canonical_readme=source_core / "README.md")


def _sync_code_tree(source: Path, destination: Path) -> _SyncStats:
    """Mirror one code tree by content while preserving excluded runtime trees."""
    stats = _SyncStats()
    if destination.exists() and not destination.is_dir():
        raise OSError(f"file blocks synchronized root: {destination}")
    if not destination.exists():
        destination.mkdir(parents=True)
        stats.created_directories += 1
    source_directories, source_files = _tree_manifest(source)
    destination_directories, destination_files = _tree_manifest(destination)

    for relative_path in sorted(destination_files.keys() - source_files.keys()):
        destination_files[relative_path].unlink()
        stats.removed_files += 1

    extra_directories = destination_directories - source_directories
    for relative_path in sorted(extra_directories, key=lambda path: len(path.parts), reverse=True):
        target = destination / relative_path
        try:
            target.rmdir()
        except OSError:
            continue
        stats.removed_directories += 1

    for relative_path in sorted(source_directories, key=lambda path: len(path.parts)):
        target = destination / relative_path
        if target.is_dir():
            continue
        if target.exists():
            target.unlink()
            stats.removed_files += 1
        target.mkdir()
        stats.created_directories += 1

    for relative_path, source_file in sorted(source_files.items()):
        target = destination / relative_path
        if target.is_dir():
            raise OSError(f"directory blocks synchronized file: {target}")
        if target.is_file() and _files_match(source_file, target):
            stats.unchanged_files += 1
            continue
        temporary = target.with_name(f".{target.name}.updating-{uuid.uuid4().hex}")
        try:
            shutil.copy2(source_file, temporary)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
        stats.copied_files += 1

    return stats


def _tree_manifest(root: Path) -> tuple[set[Path], dict[Path, Path]]:
    """Return relative directory and file manifests without transient content."""
    directories: set[Path] = set()
    files: dict[Path, Path] = {}
    for directory, names, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(directory)
        relative_directory = current.relative_to(root)
        if relative_directory != Path("."):
            directories.add(relative_directory)

        accepted_names: list[str] = []
        for name in names:
            child = current / name
            if _is_excluded_tree_entry(current, name):
                continue
            if child.is_symlink():
                raise ValueError(f"symbolic links are not supported in update-agent: {child}")
            accepted_names.append(name)
        names[:] = accepted_names

        for filename in filenames:
            if _is_excluded_tree_entry(current, filename):
                continue
            child = current / filename
            if child.is_symlink():
                raise ValueError(f"symbolic links are not supported in update-agent: {child}")
            files[child.relative_to(root)] = child
    return directories, files


def _is_excluded_tree_entry(directory: Path, name: str) -> bool:
    """Identify transient entries excluded from create and update operations."""
    if name in COPY_EXCLUDED_NAMES or name.endswith((".pyc", ".pyo")):
        return True
    return directory.name == "documentation" and name == "wiki"


def _files_match(left: Path, right: Path) -> bool:
    """Return whether two regular files have identical bytes."""
    if left.stat().st_size != right.stat().st_size:
        return False
    return _sha256(left) == _sha256(right)


def _sha256(path: Path) -> str:
    """Return a streaming SHA-256 digest for one file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_seed_sources(
    canonical_core: Path,
    instruction_template: Path,
    license_template: Path,
) -> None:
    """Validate required, versioned seed sources before writing a destination."""
    required = (
        canonical_core / "core_cli.py",
        canonical_core / "requirements.txt",
        canonical_core / "brain",
        canonical_core / "brain_explorer",
        canonical_core / "utilities",
        canonical_core / "assets" / "avatar",
        canonical_core / "assets" / "avatar" / "avatar_awaiting.gif",
        canonical_core / "README.md",
        *(canonical_core / "assets" / "screens" / name for name in PUBLIC_SCREEN_NAMES),
        instruction_template,
        license_template,
    )
    missing = [path.as_posix() for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"incomplete core seed; missing: {', '.join(missing)}")
    _validate_readme_contract(canonical_readme=canonical_core / "README.md")


def _validate_readme_contract(canonical_readme: Path) -> None:
    """Validate the single README source before publishing it at an agent root."""
    canonical_text = canonical_readme.read_text(encoding="utf-8")
    canonical = canonical_text.casefold()
    missing: list[str] = []
    for marker in (*README_CONTRACT_MARKERS, *PUBLIC_SCREEN_NAMES):
        normalized = marker.casefold()
        if normalized not in canonical:
            missing.append(marker)
    if missing:
        raise ValueError(f"README publication contract is incomplete: {', '.join(missing)}")
    invalid_assets: list[str] = []
    for reference in re.findall(r'<img\s+[^>]*src="([^"]+)"', canonical_text, flags=re.IGNORECASE):
        if not reference.startswith("core/"):
            invalid_assets.append(reference)
            continue
        source_asset = canonical_readme.parent / reference.removeprefix("core/")
        if not source_asset.is_file():
            invalid_assets.append(reference)
    if invalid_assets:
        raise ValueError(
            "README root-publication asset contract is invalid: "
            f"{', '.join(sorted(set(invalid_assets)))}",
        )


def _remove_failed_seed(temporary_root: Path) -> None:
    """Best-effort cleanup for the factory's own unpublished temporary tree."""
    last_error: OSError | None = None
    for attempt in range(3):
        if not temporary_root.exists():
            return
        try:
            shutil.rmtree(temporary_root)
            return
        except OSError as exc:
            last_error = exc
            time.sleep(0.1 * (attempt + 1))
    if last_error is not None:
        raise last_error


def _publish_seed(temporary_root: Path, agent_root: Path) -> None:
    """Rename the complete staging tree without replacing an existing agent."""
    last_error: PermissionError | None = None
    for attempt in range(12):
        if agent_root.exists():
            raise FileExistsError(f"destination appeared during creation: {agent_root}")
        try:
            temporary_root.rename(agent_root)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.1 * (attempt + 1))
    if last_error is not None:
        raise last_error


def _copy_core_seed(source: Path, destination: Path) -> None:
    """Copy versioned core code while excluding personal and generated state."""
    destination.mkdir(parents=True)
    for item in source.iterdir():
        if (
            item.name in CORE_OWNED_ROOTS
            or item.name in COPY_EXCLUDED_NAMES
            or item.name in CORE_SEED_EXCLUDED_ROOT_NAMES
        ):
            continue
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target, ignore=_copy_ignore)
        else:
            shutil.copy2(item, target)


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    """Exclude caches, dependencies, and generated wiki trees from a seed copy."""
    ignored = {name for name in names if name in COPY_EXCLUDED_NAMES}
    if Path(_directory).name == "documentation" and "wiki" in names:
        ignored.add("wiki")
    ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
    return ignored


def _write_agent_configuration(
    agent_root: Path,
    final_agent_root: Path,
    agent_name: str,
    user_name: str,
) -> None:
    """Write default, versionable configuration for the new core."""
    configs = agent_root / "core" / "configs"
    configs.mkdir(parents=True)
    _write_json(
        configs / "brain_configs.json",
        default_brain_config(final_agent_root, agent_name, user_name),
    )
    _write_json(configs / "brain_avatar_config.json", default_avatar_config(final_agent_root))
    _write_json(
        configs / "brain_mirrors.json",
        [{"name": f"@{agent_name}", "path": final_agent_root.as_posix()}],
    )


def _create_empty_core_state(core_root: Path, *, source_core: Path) -> None:
    """Create empty stores and install versioned presentation state assets."""
    database = core_root / "database"
    database.mkdir()
    (database / ".gitignore").write_text(DATABASE_GITIGNORE, encoding="utf-8")
    for store_name in PRIVATE_STORE_NAMES:
        store = database / store_name
        store.mkdir()
        (store / ".gitignore").write_text(PRIVATE_STORE_GITIGNORE, encoding="utf-8")

    registry = database / "instruction_mirrors"
    registry.mkdir()
    (registry / "agent_prompt_mirrors.txt").write_text(
        "# Add one absolute AGENTS.md mirror destination per line.\n",
        encoding="utf-8",
    )

    avatar_assets = core_root / "assets" / "avatar"
    avatar_assets.mkdir(parents=True)
    copied_assets = 0
    for source_asset in sorted((source_core / "assets" / "avatar").iterdir()):
        is_contract_document = source_asset.name.casefold() == "readme.md"
        is_state_image = AVATAR_STATE_PATTERN.fullmatch(source_asset.name) is not None
        if not source_asset.is_file() or not (is_contract_document or is_state_image):
            continue
        shutil.copy2(source_asset, avatar_assets / source_asset.name)
        copied_assets += 1
    if copied_assets == 0:
        (avatar_assets / ".gitkeep").write_text("", encoding="utf-8")

    screen_assets = core_root / "assets" / "screens"
    screen_assets.mkdir(parents=True)
    for screen_name in PUBLIC_SCREEN_NAMES:
        shutil.copy2(source_core / "assets" / "screens" / screen_name, screen_assets / screen_name)


def _create_agent_authored_structure(agent_root: Path) -> None:
    """Create empty authored-state directories expected by a generic agent."""
    for relative in (
        "memory",
        "memory/profiles",
        "memory/diary",
        "snippets",
        "skills",
        "workflows",
        "pictures",
        "$workspaces",
        "$user",
        ".tmp",
    ):
        directory = agent_root / relative
        directory.mkdir()
        (directory / ".gitkeep").write_text("", encoding="utf-8")


def _read_agent_identity(agent_root: Path) -> tuple[str, str]:
    """Read the receiving agent and user names from its canonical configuration."""
    config_path = agent_root / "core" / "configs" / "brain_configs.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    agent_name = normalize_agent_name(str(payload.get("agent_name", "")))
    user_name = normalize_user_name(str(payload.get("user_name", "")))
    return agent_name, user_name


def _sync_agent_prompt(
    template: Path,
    destination: Path,
    agent_name: str,
    user_name: str,
) -> _SyncStats:
    """Render only agent/user identity placeholders into the canonical prompt."""
    content = template.read_text(encoding="utf-8")
    rendered = content.replace("{{AGENT_NAME}}", agent_name).replace("{{USER_NAME}}", user_name)
    if "{{AGENT_NAME}}" in rendered or "{{USER_NAME}}" in rendered:
        raise ValueError("unresolved identity placeholder in generic AGENTS.md template")
    encoded = rendered.encode("utf-8")

    stats = _SyncStats()
    if destination.is_dir():
        raise OSError(f"directory blocks synchronized AGENTS template: {destination}")
    if destination.is_file() and destination.read_bytes() == encoded:
        stats.unchanged_files += 1
        return stats

    temporary = destination.with_name(f".{destination.name}.updating-{uuid.uuid4().hex}")
    try:
        temporary.write_bytes(encoded)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    stats.copied_files += 1
    return stats

def _publication_contents(readme_source: Path) -> dict[str, str]:
    """Read the single canonical README and canonical AGPL license."""
    return {
        "README.md": readme_source.read_text(encoding="utf-8"),
        "LICENSE": LICENSE_TEMPLATE.read_text(encoding="utf-8"),
    }


def _write_publication_files(agent_root: Path, readme_source: Path) -> None:
    """Copy the core README and canonical AGPL v3 license to a new clone root."""
    for file_name, content in _publication_contents(readme_source).items():
        (agent_root / file_name).write_text(content, encoding="utf-8")


def _sync_publication_files(agent_root: Path, readme_source: Path) -> _SyncStats:
    """Atomically overwrite changed canonical root publication files."""
    stats = _SyncStats()
    for file_name, content in _publication_contents(readme_source).items():
        destination = agent_root / file_name
        encoded = content.encode("utf-8")
        if destination.is_file() and destination.read_bytes() == encoded:
            stats.unchanged_files += 1
            continue
        if destination.is_dir():
            raise OSError(f"directory blocks synchronized publication file: {destination}")
        temporary = destination.with_name(f".{destination.name}.updating-{uuid.uuid4().hex}")
        try:
            temporary.write_bytes(encoded)
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        stats.copied_files += 1
    return stats


def _create_agent_consumer(agent_root: Path) -> Path:
    """Create the new agent's root consumer through its cloned Brain CLI.

    Args:
        agent_root (Path): Newly published agent directory and consumer root.

    Returns:
        Path: Expected consumer launcher created by `create-brain`.
    """
    core_cli = agent_root / "core" / "core_cli.py"
    command = [sys.executable, str(core_cli), "create-brain", str(agent_root), "--json"]
    _run_brain_lifecycle(command=command, cwd=agent_root, operation="create-brain")
    return agent_root / "$agent" / "scripts" / "brain.py"


def _initialize_agent_consumer(agent_root: Path) -> None:
    """Initialize an updated agent through its existing consumer launcher.

    Args:
        agent_root (Path): Updated agent directory that owns the consumer.

    Raises:
        FileNotFoundError: If the agent does not contain a consumer launcher.
    """
    launcher = agent_root / "$agent" / "scripts" / "brain.py"
    if not launcher.is_file():
        return
    command = [sys.executable, str(launcher), "init", "--json"]
    _run_brain_lifecycle(command=command, cwd=agent_root, operation="init")


def _run_brain_lifecycle(command: list[str], cwd: Path, operation: str) -> None:
    """Run one Brain lifecycle command without inheritable capture pipes.

    Args:
        command (list[str]): Explicit interpreter and Brain CLI arguments.
        cwd (Path): Agent root used as the child process working directory.
        operation (str): Lifecycle name included in failure diagnostics.

    Raises:
        RuntimeError: If the Brain lifecycle command returns a nonzero status.
    """
    with tempfile.TemporaryFile(mode="w+b") as diagnostic_stream:
        result = subprocess.run(
            command,
            cwd=cwd,
            stdout=diagnostic_stream,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode == 0:
            return

        diagnostic_stream.seek(0)
        diagnostic = diagnostic_stream.read().decode("utf-8", errors="replace").strip()
    detail = diagnostic or "no diagnostic output"
    raise RuntimeError(f"Brain {operation} failed with exit code {result.returncode}: {detail[-2000:]}")

def _write_json(path: Path, payload: object) -> None:
    """Write stable UTF-8 JSON with a trailing newline."""
    path.write_text(f"{json.dumps(payload, indent=2, ensure_ascii=False)}\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the standalone agent-directory factory command.

    Args:
        argv (Sequence[str] | None): Explicit arguments, or None to use process
            arguments.

    Returns:
        int: Zero when creation or update succeeds; otherwise one.
    """
    args = parse_cli_args(argv)
    try:
        if args.command == "update-agent":
            result = update_agent(Path(args.path))
        else:
            result = create_agent_directory(
                parent_path=Path(args.path),
                agent_name=args.agent_name,
                user_name=args.user_name,
            )
    except (FileExistsError, FileNotFoundError, OSError, ValueError) as exc:
        if args.json:
            print(json.dumps({"ok": False, "command": args.command, "error": str(exc)}))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    payload = {"ok": True, "command": args.command, **asdict(result)}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        if isinstance(result, UpdateAgentResult):
            print(
                f"Updated {result.target_core}: {result.copied_files} copied, "
                f"{result.unchanged_files} unchanged, {result.removed_files} removed",
            )
        else:
            print(f"Created {result.agent_name} at {result.agent_root}")
            print(f"Brain consumer: {result.consumer_entrypoint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
