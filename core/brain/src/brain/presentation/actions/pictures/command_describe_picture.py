"""Persist manual or model-backed picture descriptions."""

from __future__ import annotations

import argparse
import json

from brain.application.pictures.descriptions import set_picture_description
from brain.infrastructure.vectorstores.pictures import sync_picture_vectors


def handle(args: argparse.Namespace) -> int:
    """Describe one picture and refresh its semantic reference."""
    try:
        record = set_picture_description(
            picture_id=str(args.picture_id),
            description=str(getattr(args, "description", "") or ""),
            prompt=str(getattr(args, "prompt", "") or ""),
        )
        vectors = sync_picture_vectors()
        payload = {"ok": True, "command": "describe-picture", "picture": record.as_mapping(), "vectors": vectors}
        exit_code = 0
    except Exception as exc:
        payload = {"ok": False, "command": "describe-picture", "error": str(exc)}
        exit_code = 1
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif payload["ok"]:
        print(f"Updated picture description: {payload['picture']['relative_path']}")
    else:
        print(f"Error: {payload['error']}")
    return exit_code
