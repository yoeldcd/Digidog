"""Manual and model-backed picture description workflows."""

from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from brain.application.knowledge.runtime.config_store import resolve_secret
from brain.application.pictures.config import load_pictures_config
from brain.infrastructure.pictures.models import PictureRecord
from brain.infrastructure.pictures.repository import PictureRepository
from brain.infrastructure.runtime.paths import get_pictures_dir


DEFAULT_DESCRIPTION_PROMPT = (
    "Describe this image for a personal knowledge index. Identify the main subjects, "
    "setting, activity, visible objects, colors, mood, and any legible text. Be factual, "
    "concise, and useful for semantic search. Do not infer sensitive attributes."
)


def set_picture_description(
    picture_id: str,
    description: str = "",
    prompt: str = "",
    repository: PictureRepository | None = None,
    pictures_root: Path | None = None,
) -> PictureRecord:
    """Persist a manual description or generate one with the configured vision model."""
    repo = repository or PictureRepository()
    record = repo.get(picture_id=picture_id)
    if record is None or not record.active:
        raise ValueError(f"Unknown active picture `{picture_id}`.")

    normalized_description = description.strip()
    source = "manual"
    if not normalized_description:
        root = (pictures_root or get_pictures_dir()).resolve()
        normalized_description = _generate_description(
            picture_path=(root / record.relative_path).resolve(),
            mime_type=record.mime_type,
            prompt=prompt.strip() or DEFAULT_DESCRIPTION_PROMPT,
        )
        source = "image_model"
    described_at = datetime.now().astimezone().isoformat()
    return repo.update_description(
        picture_id=record.id,
        description=normalized_description,
        source=source,
        described_at=described_at,
    )


def _generate_description(picture_path: Path, mime_type: str, prompt: str) -> str:
    """Call the configured OpenAI-compatible img2text model for one image."""
    config = load_pictures_config().image_model
    if not config.enabled:
        raise ValueError("Picture image_model is disabled; provide a manual description or enable it in brain_configs.")
    api_key = resolve_secret(config.api_key)
    if not api_key or api_key.startswith("$"):
        raise ValueError("Picture image_model API key is unavailable.")
    encoded = base64.b64encode(picture_path.read_bytes()).decode("ascii")
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
                ],
            },
        ],
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }
    response = requests.post(
        f"{config.base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    content = str(data["choices"][0]["message"]["content"]).strip()
    if not content:
        raise ValueError("Picture image_model returned an empty description.")
    return content
