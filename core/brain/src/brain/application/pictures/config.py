"""Typed access to picture runtime configuration."""

from __future__ import annotations

import json

from brain.application.knowledge.models.dtos.runtime_config import BrainConfigsDTO, PicturesConfigDTO
from brain.infrastructure.runtime.paths import get_brain_configs_path


def load_pictures_config() -> PicturesConfigDTO:
    """Load and validate the unified `pictures` configuration section."""
    raw_data = json.loads(get_brain_configs_path().read_text(encoding="utf-8"))
    return BrainConfigsDTO.model_validate(raw_data).pictures
