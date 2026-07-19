"""Read and mutate environment-specific picture recognition guidance."""

from __future__ import annotations

import json
from pathlib import Path

from brain.application.knowledge.models.dtos.runtime_config import (
    BrainConfigsDTO,
    PictureGuidanceConfigDTO,
)
from brain.infrastructure.runtime.paths import get_brain_configs_path


GUIDANCE_SECTIONS = ("tags", "characters")
"""Supported picture guidance collections exposed by the CLI."""


def list_picture_guidance(section: str = "") -> dict[str, dict[str, str]]:
    """
    Return all guidance or one selected collection.

    Args:
        section: Optional `tags` or `characters` collection name.

    Returns:
        Mapping of guidance collection names to their entries.
    """
    guidance = _load_brain_configs().pictures.guidance
    if not section:
        return guidance.model_dump()
    normalized_section = _normalize_section(section=section)
    return {normalized_section: dict(getattr(guidance, normalized_section))}


def set_picture_guidance_entry(section: str, name: str, description: str) -> dict[str, str]:
    """
    Create or replace one picture guidance entry.

    Args:
        section: Target `tags` or `characters` collection.
        name: Stable entry label or known character name.
        description: Observable visual criteria supplied to img2text.

    Returns:
        Persisted entry mapping.
    """
    normalized_section = _normalize_section(section=section)
    normalized_name = _required_text(value=name, field_name="name")
    normalized_description = _required_text(value=description, field_name="description")
    brain_configs = _load_brain_configs()
    entries = dict(getattr(brain_configs.pictures.guidance, normalized_section))
    entries[normalized_name] = normalized_description
    setattr(brain_configs.pictures.guidance, normalized_section, entries)
    _save_brain_configs(brain_configs=brain_configs)
    return {"section": normalized_section, "name": normalized_name, "description": normalized_description}


def delete_picture_guidance_entry(section: str, name: str) -> dict[str, str]:
    """
    Delete one existing picture guidance entry.

    Args:
        section: Target `tags` or `characters` collection.
        name: Existing entry label.

    Returns:
        Deleted entry mapping.

    Raises:
        ValueError: If the requested entry does not exist.
    """
    normalized_section = _normalize_section(section=section)
    normalized_name = _required_text(value=name, field_name="name")
    brain_configs = _load_brain_configs()
    entries = dict(getattr(brain_configs.pictures.guidance, normalized_section))
    if normalized_name not in entries:
        raise ValueError(f"Unknown picture guidance {normalized_section} entry `{normalized_name}`.")
    description = entries.pop(normalized_name)
    setattr(brain_configs.pictures.guidance, normalized_section, entries)
    _save_brain_configs(brain_configs=brain_configs)
    return {"section": normalized_section, "name": normalized_name, "description": description}


def _load_brain_configs(config_path: Path | None = None) -> BrainConfigsDTO:
    """Load and validate the unified runtime configuration."""
    resolved_path = config_path or get_brain_configs_path()
    raw_data = json.loads(resolved_path.read_text(encoding="utf-8"))
    return BrainConfigsDTO.model_validate(raw_data)


def _save_brain_configs(brain_configs: BrainConfigsDTO, config_path: Path | None = None) -> None:
    """Persist validated runtime configuration with a replace-safe temporary file."""
    resolved_path = config_path or get_brain_configs_path()
    temporary_path = resolved_path.with_suffix(f"{resolved_path.suffix}.tmp")
    temporary_path.write_text(f"{brain_configs.model_dump_json(indent=2)}\n", encoding="utf-8")
    temporary_path.replace(resolved_path)


def _normalize_section(section: str) -> str:
    """Validate and normalize one guidance collection name."""
    normalized = section.strip().casefold()
    if normalized not in GUIDANCE_SECTIONS:
        raise ValueError(f"Picture guidance section must be one of: {', '.join(GUIDANCE_SECTIONS)}.")
    return normalized


def _required_text(value: str, field_name: str) -> str:
    """Return one non-empty trimmed command value."""
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"Picture guidance {field_name} cannot be blank.")
    return normalized
