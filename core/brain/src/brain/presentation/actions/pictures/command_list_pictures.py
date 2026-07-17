"""List registered picture records."""

from __future__ import annotations

import argparse
import json

from brain.infrastructure.pictures.repository import PictureRepository
from brain.infrastructure.pictures.scanner import scan_pictures


def handle(args: argparse.Namespace) -> int:
    """Print bounded picture records after a lightweight incremental scan."""
    scan_pictures()
    repository = PictureRepository()
    picture_id = str(getattr(args, "id", "") or "")
    if picture_id:
        record = repository.get(picture_id=picture_id)
        records = [record] if record is not None else []
    elif str(getattr(args, "query", "") or ""):
        records = repository.search(
            query=str(args.query), domain=str(getattr(args, "domain", "") or ""), limit=int(args.limit),
        )
    else:
        records = repository.list(
            domain=str(getattr(args, "domain", "") or ""), active_only=not bool(getattr(args, "all", False)),
        )[: max(1, min(int(args.limit), 500))]
    payload = {
        "ok": True, "command": "list-pictures", "database": repository.database_path.as_posix(),
        "count": len(records), "pictures": [record.as_mapping() for record in records],
    }
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for record in records:
            suffix = f" — {record.description}" if record.description else ""
            print(f"- {record.id} [{record.domain}] {record.relative_path}{suffix}")
    return 0
