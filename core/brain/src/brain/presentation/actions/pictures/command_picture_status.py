"""Report picture registry health and configuration."""

from __future__ import annotations

import argparse
import json

from brain.application.pictures.config import load_pictures_config
from brain.infrastructure.pictures.repository import PictureRepository
from brain.infrastructure.pictures.scanner import scan_pictures


def handle(args: argparse.Namespace) -> int:
    """Print counts by domain and description state."""
    scan = scan_pictures()
    repository = PictureRepository()
    records = repository.list()
    domains: dict[str, int] = {}
    for record in records:
        domains[record.domain] = domains.get(record.domain, 0) + 1
    config = load_pictures_config()
    payload = {
        "ok": not bool(scan["errors"]), "command": "picture-status", "database": repository.database_path.as_posix(),
        "root": scan["root"], "total": len(records), "described": sum(bool(record.description) for record in records),
        "domains": domains, "image_model": {"model": config.image_model.model, "enabled": config.image_model.enabled},
        "supported_extensions": config.supported_extensions, "scan": scan,
    }
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Pictures: {payload['total']} active, {payload['described']} described across {len(domains)} domains.")
    return 0 if payload["ok"] else 1
