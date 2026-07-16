# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Action module to show the local vector store configuration and statistics."""

from __future__ import annotations

import argparse
import json
from brain.infrastructure.runtime.paths import get_vectorstore_dir, get_workspace_root
from brain.infrastructure.vectorstores.settings import load_config
from brain.infrastructure.vectorstores.manager import VectorStoreManager
from brain.presentation.terminal import render_placeholders, log_step




def handle(args: argparse.Namespace) -> int:
    """Execute status command for local vector store."""
    color_enabled = getattr(args, "color", False)
    log_step(args, 'Retrieving local vectorstore status...')
    try:
        workspace_root = get_workspace_root()
        db_path = get_vectorstore_dir(scope="local", workspace_root=workspace_root)

        # Instantiate with default to inspect client collections
        manager = VectorStoreManager(db_path=db_path, collection_name="logs")

        # Pull details of all collections in the local database
        collections_info = []
        try:
            collections = manager.client.list_collections()
            for col in collections:
                collections_info.append({
                    "name": col.name,
                    "count": col.count()
                })
        except Exception as e:
            collections_info = [{"name": "logs", "count": 0, "error": str(e)}]

        config = load_config()
        emb_config = config.get("embedding_model", {})
        emb_model = emb_config.get("model", "openai/text-embedding-3-small")
        emb_url = emb_config.get("base_url", "https://openrouter.ai/api/v1")

        if args.json:
            print(json.dumps({
                "ok": True,
                "vectorstore_path": str(db_path),
                "collections": collections_info,
                "embedding_model": {
                    "model": emb_model,
                    "base_url": emb_url
                }
            }, ensure_ascii=False, indent=2))
        else:
            border = " __MAGENTA__+-------------------------------------------------------+__RESET__"
            title = " __BOLD____CYAN__            LOCAL VECTORSTORE SYSTEM STATUS            __RESET__"

            output = [
                border,
                title,
                border,
                f"  __BOLD__Status:__RESET__          __GREEN__ACTIVE / OPERATIONAL__RESET__",
                f"  __BOLD__Vector DB Path:__RESET__  __YELLOW__$agent/database/brain_vectorstore__RESET__",
            ]

            output.append("  __BOLD__Collections:__RESET__")
            for col in collections_info:
                output.append(f"    - __CYAN__'{col['name']}'__RESET__: __GREEN__{col['count']} chunks__RESET__")

            output.extend([
                border,
                " __BOLD____CYAN__              MODEL CONFIGURATION DETAILS              __RESET__",
                border,
                f"  __BOLD__Embedding Model:__RESET__",
                f"    - Model:    __YELLOW__{emb_model}__RESET__",
                f"    - Endpoint: __DIM__{emb_url}__RESET__",
                border
            ])

            print("\n".join(render_placeholders(line, color_enabled) for line in output))

        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            msg = f"__RED__Error retrieving local vectorstore status: {exc}__RESET__"
            print(render_placeholders(msg, color_enabled))
        return 1
