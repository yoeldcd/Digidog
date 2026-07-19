"""Persist manual or model-backed picture descriptions."""

from __future__ import annotations

import argparse
import json
from functools import partial

from brain.application.pictures.descriptions import describe_registered_pictures, set_picture_description
from brain.infrastructure.pictures.models import PictureRecord
from brain.presentation.terminal import log_step, log_verbose
from brain.infrastructure.vectorstores.pictures import sync_picture_vectors


COMMAND_NAME = "describe-image"


def _verbose_step(args: argparse.Namespace, message: str) -> None:
    """Emit one human-readable progress step without corrupting JSON output."""
    if not getattr(args, "json", False):
        log_step(args, message, task=COMMAND_NAME)


def _verbose_picture(args: argparse.Namespace, index: int, total: int, record: PictureRecord) -> None:
    """Emit the concrete picture currently sent to img2text."""
    if not getattr(args, "json", False):
        log_verbose(args, f"  [{index}/{total}] Describing {record.relative_path} ({record.id})")


def _validate_mode(args: argparse.Namespace) -> tuple[bool, bool]:
    """Validate mutually exclusive single and batch description inputs."""
    describe_all = bool(getattr(args, "all", False))
    undescribed = bool(getattr(args, "undescribeds", False))
    picture_id = str(getattr(args, "picture_id", "") or "").strip()
    description = str(getattr(args, "description", "") or "").strip()
    if describe_all and undescribed:
        raise ValueError("`--all` and `--undescribeds` are mutually exclusive.")
    if (describe_all or undescribed) and (picture_id or description):
        raise ValueError("Batch description flags cannot be combined with PICTURE_ID or DESCRIPTION.")
    if not describe_all and not undescribed and not picture_id:
        raise ValueError("PICTURE_ID is required unless `--all` or `--undescribeds` is used.")
    return describe_all, undescribed


def handle(args: argparse.Namespace) -> int:
    """Describe one or many pictures and refresh semantic references once."""
    try:
        describe_all, undescribed = _validate_mode(args)
        prompt = str(getattr(args, "prompt", "") or "")
        if describe_all or undescribed:
            _verbose_step(args, "[1/3] Selecting active image records...")
            batch = describe_registered_pictures(
                only_undescribed=undescribed,
                prompt=prompt,
                on_progress=partial(_verbose_picture, args),
            )
            _verbose_step(args, "[2/3] Refreshing changed picture vectors...")
            vectors = sync_picture_vectors() if int(batch["described"]) else None
            _verbose_step(args, "[3/3] Finalizing batch description summary...")
            payload = {"ok": bool(batch["ok"]), "command": COMMAND_NAME, "batch": batch, "vectors": vectors}
            exit_code = 0 if payload["ok"] else 1
        else:
            _verbose_step(args, "[1/2] Describing registered image...")
            record = set_picture_description(
                picture_id=str(args.picture_id),
                description=str(getattr(args, "description", "") or ""),
                prompt=prompt,
            )
            _verbose_picture(args, 1, 1, record)
            _verbose_step(args, "[2/2] Refreshing changed picture vectors...")
            vectors = sync_picture_vectors()
            payload = {"ok": True, "command": COMMAND_NAME, "picture": record.as_mapping(), "vectors": vectors}
            exit_code = 0
    except Exception as exc:
        payload = {"ok": False, "command": COMMAND_NAME, "error": str(exc)}
        exit_code = 1
    args.json_payload = payload
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif payload["ok"]:
        if "batch" in payload:
            batch = payload["batch"]
            print(
                f"Described {batch['described']} of {batch['requested']} requested images; "
                f"skipped {batch['skipped']}, failed {batch['failed']}."
            )
        else:
            print(f"Updated image description: {payload['picture']['relative_path']}")
    else:
        if "batch" in payload:
            batch = payload["batch"]
            print(f"Description batch completed with {batch['failed']} failures.")
        else:
            print(f"Error: {payload['error']}")
    return exit_code
