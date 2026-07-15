"""Action module to show the vector store configuration and statistics."""

from __future__ import annotations

import argparse
import json
from brain.infrastructure.vectorstores.settings import load_config
from brain.infrastructure.vectorstores.manager import VectorStoreManager
from brain.infrastructure.runtime.paths import get_vectorstore_dir
from brain.presentation.terminal import render_placeholders, log_step



def handle(args: argparse.Namespace) -> int:
    """Execute status command."""
    color_enabled = getattr(args, "color", False)
    log_step(args, 'Retrieving vectorstore status...')
    try:
        config = load_config()
        emb_config = config.get("embedding_model", {})
        txt_config = config.get("text_model", {})

        manager = VectorStoreManager()
        vectorstore_path = get_vectorstore_dir(scope="global", create=False)
        vector_count = manager.collection.count()

        # Pull details
        emb_model = emb_config.get("model", "openai/text-embedding-3-small")
        emb_url = emb_config.get("base_url", "https://openrouter.ai/api/v1")

        txt_model = txt_config.get("model", "google/gemini-2.5-flash")
        txt_url = txt_config.get("base_url", "https://openrouter.ai/api/v1")

        if args.json:
            print(json.dumps({
                "ok": True,
                "vectorstore_path": vectorstore_path.as_posix(),
                "vector_count": vector_count,
                "embedding_model": {
                    "model": emb_model,
                    "base_url": emb_url
                },
                "text_model": {
                    "model": txt_model,
                    "base_url": txt_url
                }
            }, ensure_ascii=False, indent=2))
        else:
            # Custom styled dashboard
            border = " __MAGENTA__+-------------------------------------------------------+__RESET__"
            title = " __BOLD____CYAN__               VECTORSTORE SYSTEM STATUS               __RESET__"

            output = [
                border,
                title,
                border,
                f"  __BOLD__Status:__RESET__          __GREEN__ACTIVE / OPERATIONAL__RESET__",
                f"  __BOLD__Vector DB Path:__RESET__  __YELLOW__{vectorstore_path.as_posix()}__RESET__",
                f"  __BOLD__Total Vectors:__RESET__   __GREEN__{vector_count} chunks__RESET__",
                border,
                " __BOLD____CYAN__              MODEL CONFIGURATION DETAILS              __RESET__",
                border,
                f"  __BOLD__Embedding Model:__RESET__",
                f"    - Model:    __YELLOW__{emb_model}__RESET__",
                f"    - Endpoint: __DIM__{emb_url}__RESET__",
                "",
                f"  __BOLD__Text Model:__RESET__",
                f"    - Model:    __YELLOW__{txt_model}__RESET__",
                f"    - Endpoint: __DIM__{txt_url}__RESET__",
                border
            ]
            print("\n".join(render_placeholders(line, color_enabled) for line in output))

        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            msg = f"__RED__Error retrieving vectorstore status: {exc}__RESET__"
            print(render_placeholders(msg, color_enabled))
        return 1
