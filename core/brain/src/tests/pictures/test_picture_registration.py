"""Focused contracts for scoped canonical picture registration."""

from __future__ import annotations

import base64
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from brain.application.pictures.descriptions import DEFAULT_DESCRIPTION_PROMPT
from brain.application.pictures.registration import register_picture
from brain.infrastructure.pictures.repository import PictureRepository


class PictureRegistrationTests(unittest.TestCase):
    """Verify placement, scope isolation, source validation, and idempotency."""

    def test_file_registration_uses_local_images_root_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            agent_home = workspace / "agent"
            source = workspace / "sensor.png"
            Image.new("RGB", (18, 12), (244, 122, 170)).save(source)
            repository = PictureRepository(database_path=workspace / "registry.db")

            first = register_picture(
                image_file=source,
                scope="local",
                domain="inventory.breakfast",
                description="**Subjects:** sensor calibration diagram.",
                repository=repository,
                agent_home=agent_home,
            )
            target = agent_home / "pictures" / "images" / "inventory" / "breakfast" / "sensor.png"
            self.assertTrue(target.is_file())
            self.assertEqual(first.scope, "local")
            self.assertEqual(first.relative_path, "images/inventory/breakfast/sensor.png")

            second = register_picture(
                image_file=source,
                scope="local",
                domain="inventory.breakfast",
                description="**Subjects:** sensor calibration diagram.",
                repository=repository,
                agent_home=agent_home,
            )
            self.assertEqual(second.id, first.id)
            self.assertEqual(len(repository.list(scope="local")), 1)

    def test_global_registration_can_share_relative_path_with_local_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            source = workspace / "diagram.png"
            Image.new("RGB", (8, 8), (20, 40, 60)).save(source)
            repository = PictureRepository(database_path=workspace / "registry.db")

            local = register_picture(
                image_file=source,
                scope="local",
                domain="shared.diagram",
                description="local",
                repository=repository,
                agent_home=workspace / "agent",
            )
            global_record = register_picture(
                image_file=source,
                scope="global",
                domain="shared.diagram",
                description="global",
                repository=repository,
                core_root=workspace / "core",
            )

            self.assertEqual(local.relative_path, "images/shared/diagram/diagram.png")
            self.assertEqual(global_record.relative_path, "shared/diagram/diagram.png")
            self.assertEqual(local.scope, "local")
            self.assertEqual(global_record.scope, "global")
            self.assertTrue((workspace / "agent/pictures/images/shared/diagram/diagram.png").is_file())
            self.assertTrue((workspace / "core/pictures/shared/diagram/diagram.png").is_file())
            self.assertEqual(len(repository.list(scope="local")), 1)
            self.assertEqual(len(repository.list(scope="global")), 1)

    def test_base64_registration_uses_deterministic_name_and_model_description(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            image_path = workspace / "source.png"
            Image.new("RGB", (6, 5), (1, 2, 3)).save(image_path)
            encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
            repository = PictureRepository(database_path=workspace / "registry.db")
            def describe(**kwargs):
                return repository.get(picture_id=kwargs["picture_id"])

            with patch(
                "brain.application.pictures.registration.set_picture_description",
                side_effect=describe,
            ) as description_service:
                record = register_picture(
                    image_data=f"data:image/png;base64,{encoded}",
                    scope="global",
                    domain="sensor.capture",
                    repository=repository,
                    core_root=workspace / "core",
                )

            self.assertTrue(record.filename.startswith("image-"))
            self.assertEqual(record.extension, ".png")
            self.assertEqual(record.scope, "global")
            self.assertTrue((workspace / "core/pictures/sensor/capture" / record.filename).is_file())
            description_service.assert_called_once()
            self.assertEqual(description_service.call_args.kwargs["pictures_root"], (workspace / "core/pictures").resolve())

    def test_source_and_domain_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            source = workspace / "source.png"
            Image.new("RGB", (4, 4), (0, 0, 0)).save(source)
            repository = PictureRepository(database_path=workspace / "registry.db")
            with self.assertRaises(ValueError):
                register_picture(
                    image_file=source,
                    image_data="aGVsbG8=",
                    scope="local",
                    domain="safe.domain",
                    repository=repository,
                    agent_home=workspace / "agent",
                )
            with self.assertRaises(ValueError):
                register_picture(
                    image_file=source,
                    scope="local",
                    domain="../escape",
                    repository=repository,
                    agent_home=workspace / "agent",
                )

    def test_index_forces_picture_vector_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            source = workspace / "indexed.png"
            Image.new("RGB", (5, 5), (8, 9, 10)).save(source)
            repository = PictureRepository(database_path=workspace / "registry.db")

            with patch("brain.infrastructure.vectorstores.pictures.sync_picture_vectors") as sync_vectors:
                register_picture(
                    image_file=source,
                    scope="local",
                    domain="indexed.sensor",
                    description="**Subjects:** calibration sample.",
                    repository=repository,
                    agent_home=workspace / "agent",
                    index=True,
                )

            sync_vectors.assert_called_once_with()

    def test_default_prompt_exposes_explorer_semantic_fields(self) -> None:
        for label in ("**Subjects:**", "**Setting:**", "**Activity:**", "**Objects:**", "**Colors:**", "**Mood:**", "**Text:**", "**Semantic Tags:**"):
            self.assertIn(label, DEFAULT_DESCRIPTION_PROMPT)


if __name__ == "__main__":
    unittest.main()
