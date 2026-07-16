# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Render the voice catalog exposed by one avatar engine."""

from __future__ import annotations

import argparse
import json
import sys

from brain.infrastructure.voice.service import VoiceService


def handle(args: argparse.Namespace) -> int:
    """Resolve and render an engine voice catalog."""
    try:
        catalog = VoiceService().list_voices(engine_name=str(getattr(args, "engine", "") or ""))
    except Exception as exc:
        print(f"Avatar voice discovery failed: {exc}", file=sys.stderr)
        args.json_payload = {"ok": False, "command": "list-avatar-voices", "error": str(exc)}
        return 1
    active = " (active)" if catalog["active"] else ""
    print(f"Engine: {catalog['engine']} [{catalog['mode']}]{active}")
    engine_configuration = {"voices": catalog["voiceMap"], **catalog.get("settings", {})}
    print(json.dumps(engine_configuration, ensure_ascii=False, indent=2))
    if catalog["models"]:
        model_ids = [model["id"] for model in catalog["models"]]
        print(json.dumps({"models": model_ids}, ensure_ascii=False, indent=2))
    for warning in catalog.get("warnings", []):
        print(f"Discovery warning: {warning}")
    args.json_payload = {"ok": True, "command": "list-avatar-voices", **catalog}
    return 0
