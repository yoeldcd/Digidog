"""Resolve the configured text-model connection for the JSDoc build step."""

from __future__ import annotations

import json
from pathlib import Path
import sys


CORE_ROOT = Path(__file__).resolve().parents[2]
BRAIN_SOURCE_ROOT = CORE_ROOT / "brain" / "src"
sys.path.insert(0, str(BRAIN_SOURCE_ROOT))

from brain.application.knowledge.runtime.config_store import resolve_secret  # noqa: E402
from brain.application.querying.llm import load_text_model_config  # noqa: E402


def main() -> int:
    """Emit the resolved model configuration as JSON for the JavaScript builder.

    Returns:
        int: Zero after writing the model connection payload to standard output.

    Raises:
        RuntimeError: If the configured API key cannot be resolved.
    """
    config = load_text_model_config(max_tokens=900)
    api_key = resolve_secret(config.api_key)
    if not api_key or api_key.startswith("$"):
        raise RuntimeError("configured OpenRouter API key is unresolved")
    json.dump(
        {
            "model": config.model,
            "base_url": config.base_url,
            "api_key": api_key,
            "temperature": config.temperature,
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
