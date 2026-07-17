"""Focused regression tests for the incremental picture registry."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from brain.infrastructure.pictures.repository import PictureRepository
from brain.infrastructure.pictures.scanner import scan_pictures
from brain.infrastructure.explorer.routes.picture_routes import PictureRoutesMixin


class PictureRegistryTests(unittest.TestCase):
    """Verify scanning, hierarchy domains, descriptions, moves, and deletion."""

    def test_scan_preserves_manual_description_across_move_and_detects_delete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "pictures"
            database = Path(temp_dir) / "picture_storage" / "pictures.db"
            nested = root / "family" / "dinner"
            nested.mkdir(parents=True)
            original = nested / "cake.png"
            Image.new("RGB", (32, 24), (244, 122, 170)).save(original)
            repository = PictureRepository(database_path=database)

            first = scan_pictures(repository=repository, pictures_root=root)
            self.assertEqual(first["added"], 1)
            record = repository.list()[0]
            self.assertEqual(record.domain, "family.dinner")
            self.assertEqual((record.width, record.height), (32, 24))
            repository.update_description(record.id, "Chocolate cake with family.", "manual", "2026-07-17T21:00:00+03:00")

            second = scan_pictures(repository=repository, pictures_root=root)
            self.assertEqual(second["unchanged"], 1)
            moved_path = root / "family" / "cake.png"
            original.rename(moved_path)
            moved = scan_pictures(repository=repository, pictures_root=root)
            self.assertEqual(moved["moved"], 1)
            moved_record = repository.list()[0]
            self.assertEqual(moved_record.id, record.id)
            self.assertEqual(moved_record.domain, "family")
            self.assertEqual(moved_record.description, "Chocolate cake with family.")

            matches = repository.search("chocolate family")
            self.assertEqual([item.id for item in matches], [record.id])
            moved_path.unlink()
            deleted = scan_pictures(repository=repository, pictures_root=root)
            self.assertEqual(deleted["deleted"], 1)
            self.assertEqual(repository.list(), [])
            self.assertFalse(repository.get(picture_id=record.id).active)

    def test_explorer_loads_structure_once_and_domains_lazily(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "pictures"
            database = Path(temp_dir) / "picture_storage" / "pictures.db"
            (root / "family").mkdir(parents=True)
            Image.new("RGB", (20, 20), (244, 122, 170)).save(root / "family" / "cake.png")
            repository = PictureRepository(database_path=database)
            scan_pictures(repository=repository, pictures_root=root)

            routes = PictureRoutesMixin()
            with (
                patch("brain.infrastructure.explorer.routes.picture_routes.PictureRepository", return_value=repository),
                patch("brain.infrastructure.explorer.routes.picture_routes.scan_pictures", return_value={"unchanged": 1}) as scanner,
            ):
                structure = routes._pictures({"structure_only": "true"})["data"]
                family = routes._pictures({"domain": "family"})["data"]

            self.assertEqual(structure["pictures"], [])
            self.assertEqual(structure["domains"], {"family": 1})
            self.assertEqual([record["filename"] for record in family["pictures"]], ["cake.png"])
            self.assertEqual(family["domains"], {})
            scanner.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
