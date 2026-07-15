"""Embedding API client used by vectorstore managers."""

from __future__ import annotations

# Standard Libraries Imports
import json
import urllib.error
import urllib.request

# Application Modules Imports
from brain.infrastructure.vectorstores.settings import load_config


def get_embedding(text: str) -> list[float]:
    """Fetch embedding vector for the text using the configured API."""
    config = load_config()
    emb_config = config.get("embedding_model", {})

    model = emb_config.get("model", "openai/text-embedding-3-small")
    base_url = emb_config.get("base_url", "https://openrouter.ai/api/v1")
    api_key = emb_config.get("api_key", "")

    endpoint = f"{base_url.rstrip('/')}/embeddings"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model,
        "input": text.strip(),
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            return res_data["data"][0]["embedding"]
    except urllib.error.HTTPError as error:
        err_msg = error.read().decode("utf-8")
        try:
            parsed = json.loads(err_msg)
            message = parsed.get("error", {}).get("message", err_msg)
        except Exception:
            message = err_msg
        raise RuntimeError(f"Embedding API HTTP Error {error.code}: {message}") from error
    except Exception as error:
        raise RuntimeError(f"Failed to fetch embedding: {error}") from error
