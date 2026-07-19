"""Focused contracts for image-description and image-scan CLI workflows."""

from __future__ import annotations

import argparse
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from brain.infrastructure.pictures.models import PictureRecord
from brain.presentation.actions.pictures.command_describe_picture import handle as describe_image
from brain.presentation.actions.pictures.command_scan_pictures import handle as scan_images
from brain.presentation.commands.pictures.command_describe_picture import SCHEMA as DESCRIBE_IMAGE_SCHEMA
from brain.presentation.commands.pictures.command_scan_pictures import SCHEMA as SCAN_IMAGES_SCHEMA


def _record(picture_id: str = "picture-1", description: str = "") -> PictureRecord:
    """Return one deterministic active picture record for command tests."""
    return PictureRecord(
        id=picture_id,
        relative_path=f"root/{picture_id}.png",
        domain="root",
        filename=f"{picture_id}.png",
        extension=".png",
        mime_type="image/png",
        size_bytes=100,
        mtime_ns=1,
        content_hash="hash",
        width=20,
        height=20,
        description=description,
        description_source="manual" if description else "",
        described_at="",
        vector_fingerprint="",
        active=True,
        created_at="2026-07-18T00:00:00+03:00",
        updated_at="2026-07-18T00:00:00+03:00",
    )


class DescribeImageCommandTests(unittest.TestCase):
    """Validate batch selection, compatibility naming, and verbose progress."""

    def test_schema_exposes_describe_image_and_legacy_alias(self) -> None:
        self.assertEqual(DESCRIBE_IMAGE_SCHEMA.name, "describe-image")
        self.assertEqual(DESCRIBE_IMAGE_SCHEMA.aliases, ["describe-picture"])
        flags = [flag for argument in DESCRIBE_IMAGE_SCHEMA.arguments for flag in argument.flags]
        self.assertIn("--all", flags)
        self.assertIn("--undescribeds", flags)

    def test_undescribed_batch_emits_verbose_progress_and_refreshes_vectors_once(self) -> None:
        record = _record()
        batch = {
            "ok": True,
            "mode": "undescribed",
            "total": 1,
            "requested": 1,
            "described": 1,
            "failed": 0,
            "skipped": 0,
            "pictures": [record.as_mapping()],
            "errors": [],
        }
        args = argparse.Namespace(
            all=False,
            undescribeds=True,
            picture_id="",
            description="",
            prompt="",
            json=False,
            verbose_log=True,
            color=False,
        )

        def describe_batch(**kwargs):
            kwargs["on_progress"](1, 1, record)
            return batch

        with (
            patch(
                "brain.presentation.actions.pictures.command_describe_picture.describe_registered_pictures",
                side_effect=describe_batch,
            ),
            patch(
                "brain.presentation.actions.pictures.command_describe_picture.sync_picture_vectors",
                return_value={"indexed": 1},
            ) as vector_sync,
            redirect_stdout(io.StringIO()) as stdout,
        ):
            exit_code = describe_image(args)

        self.assertEqual(exit_code, 0)
        self.assertIn("describe-image steep [1/3]", stdout.getvalue())
        self.assertIn("root/picture-1.png", stdout.getvalue())
        vector_sync.assert_called_once_with()

    def test_batch_modes_are_mutually_exclusive(self) -> None:
        args = argparse.Namespace(
            all=True,
            undescribeds=True,
            picture_id="",
            description="",
            prompt="",
            json=True,
            verbose_log=True,
            color=False,
        )

        with redirect_stdout(io.StringIO()) as stdout:
            exit_code = describe_image(args)

        self.assertEqual(exit_code, 1)
        self.assertIn("mutually exclusive", stdout.getvalue())


class ScanImagesCommandTests(unittest.TestCase):
    """Validate state-first scan descriptions and object-level verbose output."""

    def test_schema_exposes_scan_image_contract_and_legacy_alias(self) -> None:
        self.assertEqual(SCAN_IMAGES_SCHEMA.name, "scan-images")
        self.assertEqual(SCAN_IMAGES_SCHEMA.aliases, ["scan-pictures"])
        flags = [flag for argument in SCAN_IMAGES_SCHEMA.arguments for flag in argument.flags]
        self.assertIn("--describe", flags)

    def test_describe_mode_scans_before_describing_and_indexes_once(self) -> None:
        record = _record()
        operations: list[str] = []
        scan_summary = {
            "added": 1,
            "changed": 0,
            "moved": 0,
            "unchanged": 0,
            "deleted": 0,
            "errors": [],
            "total": 1,
            "database": "pictures.db",
            "root": "pictures",
        }
        description_summary = {
            "ok": True,
            "mode": "undescribed",
            "total": 1,
            "requested": 1,
            "described": 1,
            "failed": 0,
            "skipped": 0,
            "pictures": [record.as_mapping()],
            "errors": [],
        }
        args = argparse.Namespace(describe=True, index=False, json=False, verbose_log=True, color=False)

        def scan(**kwargs):
            operations.append("scan")
            kwargs["on_event"]("added", record.relative_path)
            return scan_summary

        def describe(**kwargs):
            operations.append("describe")
            kwargs["on_progress"](1, 1, record)
            return description_summary

        def sync_vectors():
            operations.append("vectors")
            return {"indexed": 1}

        with (
            patch("brain.presentation.actions.pictures.command_scan_pictures.PictureRepository", return_value=object()),
            patch("brain.presentation.actions.pictures.command_scan_pictures.scan_pictures", side_effect=scan),
            patch(
                "brain.presentation.actions.pictures.command_scan_pictures.describe_registered_pictures",
                side_effect=describe,
            ),
            patch(
                "brain.presentation.actions.pictures.command_scan_pictures.sync_picture_vectors",
                side_effect=sync_vectors,
            ),
            redirect_stdout(io.StringIO()) as stdout,
        ):
            exit_code = scan_images(args)

        self.assertEqual(exit_code, 0)
        self.assertEqual(operations, ["scan", "describe", "vectors"])
        self.assertIn("added: root/picture-1.png", stdout.getvalue())
        self.assertIn("Describing root/picture-1.png", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
