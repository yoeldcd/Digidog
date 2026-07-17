"""Synchronize picture files and optionally their vectors."""

from __future__ import annotations

import argparse
import json

from brain.infrastructure.pictures.scanner import scan_pictures
from brain.infrastructure.vectorstores.pictures import sync_picture_vectors


def handle(args: argparse.Namespace) -> int:
    """Scan the image tree and print synchronization statistics."""
    scan = scan_pictures()
    payload = {"ok": not bool(scan["errors"]), "command": "scan-pictures", "scan": scan}
    if bool(getattr(args, "index", False)):
        payload["vectors"] = sync_picture_vectors()
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"Pictures: {scan['total']} active; added {scan['added']}, changed {scan['changed']}, "
            f"moved {scan['moved']}, deleted {scan['deleted']}."
        )
    return 0 if payload["ok"] else 1
