#!/usr/bin/env python
"""Create a new agent directory from the versioned core seed."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
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
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
}
SYNC_ROOT_NAMES = ("brain", "brain_explorer")
AVATAR_STATE_PATTERN = re.compile(r"^avatar_[A-Za-z0-9_-]+\.gif$", re.IGNORECASE)
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

# Workspace-local runtime state
/$agent/.tmp/
/$agent/database/
/$agent/logs/

# Generated documentation exports
/core/**/documentation/wiki/
"""
WORKSPACE_README = """# Co-located agent workspace

This `$agent/` directory is the initial local consumer for the agent root.
Use `$agent/scripts/brain.py` for Brain commands. Global configuration and
stores belong to the sibling `core/`; local workspace data belongs here.
"""


@dataclass(frozen=True)
class AgentDirectoryResult:
    """Paths created by one successful seed operation."""

    agent_name: str
    user_name: str
    agent_root: str
    core_root: str
    consumer_entrypoint: str
    configs: list[str]
    stores: list[str]


@dataclass(frozen=True)
class UpdateAgentResult:
    """Summary of one content-aware agent code synchronization."""

    agent_root: str
    source_core: str
    target_core: str
    updated_roots: list[str]
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
    """Build the standalone command parser."""
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
        help="Synchronize only brain/ and brain_explorer/ in an existing agent core.",
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
    """Parse explicit commands while preserving the original create invocation."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] not in {"create-agent", "update-agent"}:
        arguments.insert(0, "create-agent")
    return build_parser().parse_args(arguments)


def normalize_agent_name(value: str) -> str:
    """Return a safe agent identifier without its leading at sign."""
    normalized = value.strip().lstrip("@").strip()
    if not normalized or not AGENT_NAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            "agent name must match [A-Za-z0-9][A-Za-z0-9_-]* and may start with @",
        )
    return normalized


def normalize_user_name(value: str) -> str:
    """Return a non-empty display name."""
    normalized = value.strip()
    if not normalized:
        raise ValueError("user name cannot be empty")
    if any(character in normalized for character in ("\r", "\n", "\x00")):
        raise ValueError("user name must be a single line")
    return normalized


def default_model_config(model: str = "google/gemini-2.5-flash") -> dict[str, object]:
    """Return one provider-neutral runtime model configuration."""
    return {
        "model": model,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "$OPENROUTER_API_KEY",
        "temperature": 0.1,
        "max_tokens": 6000,
        "enabled": True,
    }


def default_brain_config(agent_root: Path) -> dict[str, object]:
    """Return default Brain configuration for a new agent identity."""
    return {
        "version": 1,
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
    }


def default_avatar_config(agent_root: Path | None = None) -> dict[str, object]:
    """Return generic local voice defaults without personal voice identifiers."""
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
    """Create one complete agent seed without copying live agent state."""
    safe_agent_name = normalize_agent_name(agent_name)
    safe_user_name = normalize_user_name(user_name)
    parent = parent_path.expanduser().resolve()
    agent_root = parent / f"@{safe_agent_name}"
    if agent_root.exists():
        raise FileExistsError(f"destination already exists: {agent_root}")

    canonical_core = (source_core or Path(__file__).resolve().parents[2]).resolve()
    template = (instruction_template or Path(__file__).with_name("AGENT.md")).resolve()
    _validate_seed_sources(canonical_core=canonical_core, template=template)

    parent.mkdir(parents=True, exist_ok=True)
    temporary_root = parent / f".{agent_root.name}.creating-{uuid.uuid4().hex}"
    try:
        temporary_root.mkdir()
        temporary_agent_root = temporary_root
        _copy_core_seed(canonical_core, temporary_agent_root / "core")
        _write_agent_configuration(
            agent_root=temporary_agent_root,
            final_agent_root=agent_root,
            agent_name=safe_agent_name,
        )
        _create_empty_core_state(
            temporary_agent_root / "core",
            source_core=canonical_core,
        )
        _create_agent_authored_structure(temporary_agent_root)
        _write_agent_prompt(
            template=template,
            destination=temporary_agent_root / "AGENT.md",
            agent_name=safe_agent_name,
            user_name=safe_user_name,
        )
        consumer = _create_initial_consumer(temporary_agent_root)
        (temporary_agent_root / ".gitignore").write_text(AGENT_ROOT_GITIGNORE, encoding="utf-8")
        _publish_seed(temporary_agent_root, agent_root)
    except Exception as exc:
        try:
            _remove_failed_seed(temporary_root)
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
        consumer_entrypoint=(agent_root / consumer.relative_to(temporary_root)).as_posix(),
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
    """Synchronize only changed Brain code files into one existing agent clone.

    The source is always the core containing this utility unless explicitly
    injected by a test. Configuration, databases, assets, identity, and all
    agent-authored domains remain outside the synchronization boundary.
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

    return UpdateAgentResult(
        agent_root=agent_root.as_posix(),
        source_core=canonical_core.as_posix(),
        target_core=target_core.as_posix(),
        updated_roots=list(SYNC_ROOT_NAMES),
        copied_files=total.copied_files,
        unchanged_files=total.unchanged_files,
        removed_files=total.removed_files,
        created_directories=total.created_directories,
        removed_directories=total.removed_directories,
    )


def _resolve_existing_agent(agent_path: Path) -> tuple[Path, Path]:
    """Resolve an existing agent root from either the root or core path."""
    candidate = agent_path.expanduser().resolve()
    candidate_is_core = all((candidate / root_name).is_dir() for root_name in SYNC_ROOT_NAMES)
    target_core = candidate if candidate_is_core else candidate / "core"
    agent_root = target_core.parent
    if not agent_root.is_dir() or not target_core.is_dir():
        raise FileNotFoundError(f"existing agent core not found: {target_core}")
    return agent_root, target_core


def _validate_update_sources(source_core: Path, target_core: Path) -> None:
    """Ensure both synchronization boundaries expose the required code roots."""
    missing = [
        path.as_posix()
        for core_root in (source_core, target_core)
        for root_name in SYNC_ROOT_NAMES
        if not (path := core_root / root_name).is_dir()
    ]
    if missing:
        raise FileNotFoundError(f"incomplete update boundary; missing: {', '.join(missing)}")


def _sync_code_tree(source: Path, destination: Path) -> _SyncStats:
    """Mirror one code tree by content while preserving excluded runtime trees."""
    source_directories, source_files = _tree_manifest(source)
    destination_directories, destination_files = _tree_manifest(destination)
    stats = _SyncStats()

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


def _validate_seed_sources(canonical_core: Path, template: Path) -> None:
    """Validate required, versioned seed sources before writing a destination."""
    required = (
        canonical_core / "core_cli.py",
        canonical_core / "requirements.txt",
        canonical_core / "brain",
        canonical_core / "brain_explorer",
        canonical_core / "utilities",
        canonical_core / "assets" / "avatar",
        template,
    )
    missing = [path.as_posix() for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"incomplete core seed; missing: {', '.join(missing)}")


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
        if item.name in CORE_OWNED_ROOTS or item.name in COPY_EXCLUDED_NAMES:
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
) -> None:
    """Write default, versionable configuration for the new core."""
    configs = agent_root / "core" / "configs"
    configs.mkdir(parents=True)
    _write_json(configs / "brain_configs.json", default_brain_config(final_agent_root))
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
        "# Add one absolute AGENT.md mirror destination per line.\n",
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


def _write_agent_prompt(
    template: Path,
    destination: Path,
    agent_name: str,
    user_name: str,
) -> None:
    """Render the generic instruction template for the new identity."""
    content = template.read_text(encoding="utf-8")
    content = content.replace("{{AGENT_NAME}}", agent_name).replace("{{USER_NAME}}", user_name)
    if "{{" in content or "}}" in content:
        raise ValueError("unresolved placeholder in generic AGENT.md template")
    destination.write_text(content, encoding="utf-8")


def _create_initial_consumer(agent_root: Path) -> Path:
    """Create the co-located WoSP facade without initializing any database."""
    workspace = agent_root / "$agent"
    scripts = workspace / "scripts"
    scripts.mkdir(parents=True)
    for relative in ("data", "database", "logs", ".tmp"):
        (workspace / relative).mkdir()
    (workspace / "README.md").write_text(WORKSPACE_README, encoding="utf-8")

    core_cli = agent_root / "core" / "core_cli.py"
    launcher = core_cli.read_text(encoding="utf-8")
    relative_core = Path(os.path.relpath(agent_root / "core", start=scripts)).as_posix()
    launcher, replacements = re.subn(
        r"^CORE_ROOT\s*=.*$",
        f'CORE_ROOT = (HOME_ROOT / Path("{relative_core}")).resolve()',
        launcher,
        count=1,
        flags=re.MULTILINE,
    )
    if replacements != 1:
        raise ValueError("core_cli.py does not expose the expected CORE_ROOT assignment")
    destination = scripts / "brain.py"
    destination.write_text(launcher, encoding="utf-8")
    return destination


def _write_json(path: Path, payload: object) -> None:
    """Write stable UTF-8 JSON with a trailing newline."""
    path.write_text(f"{json.dumps(payload, indent=2, ensure_ascii=False)}\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the standalone agent-directory factory."""
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
