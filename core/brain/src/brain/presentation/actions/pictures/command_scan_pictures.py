"""Synchronize picture files and optionally their vectors."""

from __future__ import annotations

import argparse
import json
from functools import partial

from brain.application.pictures.descriptions import describe_registered_pictures
from brain.infrastructure.pictures.models import PictureRecord
from brain.infrastructure.pictures.repository import PictureRepository
from brain.infrastructure.pictures.scanner import scan_pictures
from brain.infrastructure.vectorstores.pictures import sync_picture_vectors
from brain.presentation.terminal import log_step, log_verbose


COMMAND_NAME = "scan-images"


def _verbose_step(args: argparse.Namespace, message: str) -> None:
    """Emit one scan workflow step without corrupting JSON output."""
    if not getattr(args, "json", False):
        log_step(args, message, task=COMMAND_NAME)


def _verbose_scan_event(args: argparse.Namespace, state: str, reference: str) -> None:
    """Emit one concrete filesystem or registry transition."""
    if not getattr(args, "json", False):
        log_verbose(args, f"  {state}: {reference}")


def _verbose_description(args: argparse.Namespace, index: int, total: int, record: PictureRecord) -> None:
    """Emit the concrete image currently sent to img2text."""
    if not getattr(args, "json", False):
        log_verbose(args, f"  [{index}/{total}] Describing {record.relative_path} ({record.id})")


def handle(args: argparse.Namespace) -> int:
    """Scan image state, optionally describe pending records, and synchronize vectors once."""
    repository = PictureRepository()
    should_describe = bool(getattr(args, "describe", False))
    should_index = bool(getattr(args, "index", False))
    _verbose_step(args, "[1/3] Synchronizing image filesystem state...")
    scan = scan_pictures(repository=repository, on_event=partial(_verbose_scan_event, args))
    payload: dict[str, object] = {"ok": not bool(scan["errors"]), "command": COMMAND_NAME, "scan": scan}
    described_count = 0
    if should_describe:
        _verbose_step(args, "[2/3] Describing active images with empty descriptions...")
        descriptions = describe_registered_pictures(
            only_undescribed=True,
            repository=repository,
            on_progress=partial(_verbose_description, args),
        )
        payload["descriptions"] = descriptions
        described_count = int(descriptions["described"])
        payload["ok"] = bool(payload["ok"]) and bool(descriptions["ok"])
    if should_index or described_count:
        _verbose_step(args, "[3/3] Synchronizing changed picture vectors...")
        payload["vectors"] = sync_picture_vectors()
    else:
        _verbose_step(args, "[3/3] Picture vectors are already unchanged...")
    args.json_payload = payload
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"Pictures: {scan['total']} active; added {scan['added']}, changed {scan['changed']}, "
            f"moved {scan['moved']}, deleted {scan['deleted']}."
        )
        if should_describe:
            descriptions = payload["descriptions"]
            print(
                f"Descriptions: {descriptions['described']} of {descriptions['requested']} requested; "
                f"skipped {descriptions['skipped']}, failed {descriptions['failed']}."
            )
    return 0 if payload["ok"] else 1
