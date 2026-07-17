# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Knowledge graph runtime configuration loading and migration."""

from __future__ import annotations

# Standard Libraries Imports
import json
import os
from pathlib import Path

# Application Modules Imports
from brain.config import (
    BRAIN_CONFIGS_FILE_NAME,
    BRAIN_KNOWLEDGE_DB_NAME,
    DEFAULT_STAGE_NAMES,
    LEGACY_STAGE_MAX_TOKENS,
    LOCAL_SOURCES_DB_NAME,
    STRUCTURAL_EXTRACTION_STAGE_NAMES,
)
from brain.application.knowledge.models.dtos.runtime_config import (
    BrainConfigsDTO,
    KnowledgeConfigDTO,
    StageModelConfigDTO,
)
from brain.application.knowledge.runtime.scopes import get_knowledge_root, normalize_knowledge_scope
from brain.infrastructure.runtime.paths import get_brain_configs_path, get_core_root, ensure_private_directory


def get_shared_config_path(agent_home: Path | None = None) -> Path:
    """
    Return the single config path used by all knowledge scopes.

    Args:
        agent_home: Optional agent home override.

    Returns:
        Path: Global knowledge config path.
    """
    return get_brain_configs_path(agent_home=agent_home)


def get_config_path(knowledge_root: Path | None = None) -> Path:
    """
    Return the unified runtime brain config path.

    Args:
        knowledge_root: Optional global database root override.

    Returns:
        Path: Unified config path.
    """
    del knowledge_root
    return get_brain_configs_path()


def get_database_path(
    config_dto: KnowledgeConfigDTO | None = None,
    knowledge_root: Path | None = None,
    scope: str = "global",
) -> Path:
    """
    Return the fixed SQLite database path for the selected core contract.

    Args:
        config_dto: Retained compatibility argument; path fields are ignored.
        knowledge_root: Optional database root override.
        scope: Knowledge database scope.

    Returns:
        Path: SQLite database path.
    """
    normalized_scope: str = normalize_knowledge_scope(scope=scope)
    resolved_root: Path = knowledge_root or get_knowledge_root()
    del config_dto
    if normalized_scope == "local":
        return resolved_root / LOCAL_SOURCES_DB_NAME
    return resolved_root / BRAIN_KNOWLEDGE_DB_NAME


def build_default_config() -> KnowledgeConfigDTO:
    """
    Build the default per-stage model configuration.

    Returns:
        KnowledgeConfigDTO: Default runtime config.
    """
    stage_config: StageModelConfigDTO = StageModelConfigDTO()
    stages: dict[str, StageModelConfigDTO] = {
        stage_name: stage_config.model_copy(deep=True)
        for stage_name in DEFAULT_STAGE_NAMES
    }
    return KnowledgeConfigDTO(stages=stages)


def ensure_knowledge_root(knowledge_root: Path | None = None) -> Path:
    """
    Create the private database runtime directory and internal gitignore.

    Args:
        knowledge_root: Optional knowledge root override.

    Returns:
        Path: Created knowledge runtime root.
    """
    resolved_root: Path = knowledge_root or get_knowledge_root()
    return ensure_private_directory(path=resolved_root)


def ensure_knowledge_config(knowledge_root: Path | None = None) -> KnowledgeConfigDTO:
    """
    Create and validate `core/configs/brain_configs.json`.

    Args:
        knowledge_root: Optional knowledge root override.

    Returns:
        KnowledgeConfigDTO: Validated configuration.
    """
    resolved_root: Path = ensure_knowledge_root(knowledge_root=knowledge_root)
    config_path: Path = get_config_path(knowledge_root=resolved_root)
    if not config_path.exists():
        brain_configs_dto: BrainConfigsDTO = build_default_brain_configs()
        config_dto: KnowledgeConfigDTO = brain_configs_dto.knowledge
        config_text: str = brain_configs_dto.model_dump_json(indent=2)
        config_path.write_text(f"{config_text}\n", encoding="utf-8")
        return config_dto
    return load_knowledge_config(knowledge_root=resolved_root)


def load_knowledge_config(knowledge_root: Path | None = None) -> KnowledgeConfigDTO:
    """
    Load and validate `core/configs/brain_configs.json`.

    Args:
        knowledge_root: Optional knowledge root override.

    Returns:
        KnowledgeConfigDTO: Validated configuration.
    """
    resolved_root: Path = ensure_knowledge_root(knowledge_root=knowledge_root)
    config_path: Path = get_config_path(knowledge_root=resolved_root)
    if not config_path.exists():
        return ensure_knowledge_config(knowledge_root=resolved_root)

    raw_data: dict = json.loads(config_path.read_text(encoding="utf-8"))
    legacy_paths_removed: bool = _remove_legacy_path_fields(raw_data=raw_data)
    brain_configs_dto, config_dto = _parse_brain_configs(raw_data=raw_data)
    config_changed: bool = legacy_paths_removed or _backfill_knowledge_config(
        raw_data=raw_data,
        config_dto=config_dto,
    )
    if not brain_configs_dto.agent_dir.strip():
        brain_configs_dto.agent_dir = get_core_root().parent.as_posix()
        config_changed = True

    if config_changed:
        brain_configs_dto.knowledge = config_dto
        config_path.write_text(f"{brain_configs_dto.model_dump_json(indent=2)}\n", encoding="utf-8")

    return config_dto


def build_default_brain_configs() -> BrainConfigsDTO:
    """
    Build the unified config, importing legacy config files when present.

    Returns:
        BrainConfigsDTO: Unified brain runtime config.
    """
    return BrainConfigsDTO(
        agent_name=get_core_root().parent.name,
        agent_dir=get_core_root().parent.as_posix(),
        knowledge=build_default_config(),
    )


def resolve_secret(value: str) -> str:
    """
    Resolve environment-variable references inside config values.

    Args:
        value: Raw config value, optionally formatted as `$ENV_NAME`.

    Returns:
        str: Resolved environment value or original value.
    """
    if value.startswith("$"):
        env_name: str = value[1:]
        return os.environ.get(env_name, value)
    return value


def _backfill_knowledge_config(raw_data: dict, config_dto: KnowledgeConfigDTO) -> bool:
    """
    Mutate a loaded knowledge config so required defaults are present.

    Args:
        raw_data: Parsed config JSON.
        config_dto: Knowledge config DTO to backfill.

    Returns:
        bool: Whether the caller should persist the repaired config.
    """
    missing_stages: list[str] = [
        stage_name
        for stage_name in DEFAULT_STAGE_NAMES
        if stage_name not in config_dto.stages
    ]
    config_changed: bool = "knowledge" not in raw_data
    if missing_stages:
        for stage_name in missing_stages:
            config_dto.stages[stage_name] = StageModelConfigDTO()
        config_changed = True

    default_stage_config: StageModelConfigDTO = StageModelConfigDTO()
    for stage_name in STRUCTURAL_EXTRACTION_STAGE_NAMES:
        stage_config: StageModelConfigDTO | None = config_dto.stages.get(stage_name)
        if stage_config is None:
            continue
        if stage_config.max_tokens == LEGACY_STAGE_MAX_TOKENS:
            config_dto.stages[stage_name] = stage_config.model_copy(
                update={"max_tokens": default_stage_config.max_tokens},
            )
            config_changed = True

    return config_changed


def _remove_legacy_path_fields(raw_data: dict) -> bool:
    """Remove path choices that are now fixed by the core directory contract."""
    removed: bool = False
    for section_name, field_name in (
        ("knowledge", "database_name"),
        ("memory", "vectorstore_dir_name"),
    ):
        section: object = raw_data.get(section_name)
        if isinstance(section, dict) and field_name in section:
            section.pop(field_name)
            removed = True
    if "knowledge" not in raw_data and "database_name" in raw_data:
        raw_data.pop("database_name")
        removed = True
    return removed


def _parse_brain_configs(raw_data: dict) -> tuple[BrainConfigsDTO, KnowledgeConfigDTO]:
    """
    Parse current unified config data or one pre-unification knowledge object.

    Args:
        raw_data: Parsed JSON object.

    Returns:
        tuple[BrainConfigsDTO, KnowledgeConfigDTO]: Unified config and knowledge section.
    """
    if "knowledge" in raw_data:
        brain_configs_dto: BrainConfigsDTO = BrainConfigsDTO.model_validate(raw_data)
        return brain_configs_dto, brain_configs_dto.knowledge

    knowledge_dto: KnowledgeConfigDTO = KnowledgeConfigDTO.model_validate(raw_data)
    brain_configs_dto = BrainConfigsDTO(knowledge=knowledge_dto)
    return brain_configs_dto, knowledge_dto
