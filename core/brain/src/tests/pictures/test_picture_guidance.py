"""Regression tests for configurable picture recognition guidance."""

from __future__ import annotations

import json
import tempfile
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from brain.application.knowledge.models.dtos.runtime_config import (
    BrainConfigsDTO,
    PictureGuidanceConfigDTO,
    PicturesConfigDTO,
    StageModelConfigDTO,
)
from brain.application.knowledge.models.dtos.graph import EntityDTO
from brain.application.knowledge.models.dtos.sources import SourceDTO
from brain.application.pictures.descriptions import _generate_description, build_guided_description_prompt
from brain.application.pictures.guidance import (
    delete_picture_guidance_entry,
    list_picture_guidance,
    set_picture_guidance_entry,
)
from brain.infrastructure.database.knowledge.repository import KnowledgeRepository
from brain.infrastructure.pictures.guidance_graph import project_character_guidance
from brain.infrastructure.pictures.knowledge_graph import project_picture_description
from brain.presentation.actions.pictures.command_picture_guidance import handle


def test_picture_guidance_dto_accepts_tags_and_characters() -> None:
    """Validate the configured guidance shape without weakening other config fields."""
    config = BrainConfigsDTO.model_validate(
        {
            "pictures": {
                "guidance": {
                    "tags": {"love": "Visible affectionate contact."},
                    "characters": {"Angi": "Small pink canine with purple eyes."},
                },
            },
        },
    )

    assert config.pictures.guidance.tags == {"love": "Visible affectionate contact."}
    assert config.pictures.guidance.characters["Angi"].startswith("Small pink")


def test_guidance_prompt_names_known_characters_and_rejects_forced_matches() -> None:
    """Inject specific recognition criteria with explicit uncertainty safeguards."""
    guidance = PictureGuidanceConfigDTO(
        tags={"familiarity": "Relaxed coordinated interaction."},
        characters={"Angi": "Small pink canine with long floppy ears."},
    )

    prompt = build_guided_description_prompt(prompt="Describe the image.", guidance=guidance)

    assert "Known characters:" in prompt
    assert "- Angi: Small pink canine with long floppy ears." in prompt
    assert "- familiarity: Relaxed coordinated interaction." in prompt
    assert "instead of a generic subject label" in prompt
    assert "Never force a configured identity or tag" in prompt


def test_img2text_request_includes_configured_guidance() -> None:
    """Ensure the effective model request carries guidance, not only helper output."""
    pictures_config = PicturesConfigDTO(
        guidance=PictureGuidanceConfigDTO(
            tags={"love": "Visible caring contact."},
            characters={"Angi": "Small pink canine."},
        ),
        image_model=StageModelConfigDTO(model="vision-model", api_key="$TEST_KEY", enabled=True),
    )
    response = type(
        "Response",
        (),
        {
            "raise_for_status": lambda self: None,
            "json": lambda self: {"choices": [{"message": {"content": "Angi is visible."}}]},
        },
    )()
    with tempfile.TemporaryDirectory() as directory:
        image_path = Path(directory) / "image.png"
        image_path.write_bytes(b"image-bytes")
        with (
            patch("brain.application.pictures.descriptions.load_pictures_config", return_value=pictures_config),
            patch("brain.application.pictures.descriptions.resolve_secret", return_value="secret"),
            patch("brain.application.pictures.descriptions.requests.post", return_value=response) as post,
        ):
            result = _generate_description(image_path, "image/png", "Describe this image.")

    effective_prompt = post.call_args.kwargs["json"]["messages"][0]["content"][0]["text"]
    assert result == "Angi is visible."
    assert "- Angi: Small pink canine." in effective_prompt
    assert "- love: Visible caring contact." in effective_prompt


def test_guidance_crud_persists_validated_unified_config() -> None:
    """Create, list, and delete entries without bypassing the unified DTO contract."""
    with tempfile.TemporaryDirectory() as directory:
        config_path = Path(directory) / "brain_configs.json"
        config_path.write_text(f"{BrainConfigsDTO().model_dump_json(indent=2)}\n", encoding="utf-8")
        with patch("brain.application.pictures.guidance.get_brain_configs_path", return_value=config_path):
            entry = set_picture_guidance_entry("characters", "Angi", "Pink canine.")
            listed = list_picture_guidance("characters")
            deleted = delete_picture_guidance_entry("characters", "Angi")

        persisted = json.loads(config_path.read_text(encoding="utf-8"))
        assert entry["name"] == "Angi"
        assert listed == {"characters": {"Angi": "Pink canine."}}
        assert deleted["description"] == "Pink canine."
        assert persisted["pictures"]["guidance"]["characters"] == {}


def test_character_guidance_projects_description_to_same_name_noun() -> None:
    """Create typed graph objects and reuse the stable noun identity by name."""
    with tempfile.TemporaryDirectory() as directory:
        repository = KnowledgeRepository(db_path=Path(directory) / "knowledge.db")
        result = project_character_guidance(
            name="Angi",
            description="Small pink canine with purple eyes.",
            repository=repository,
        )
        repeated = project_character_guidance(
            name="Angi",
            description="Small pink canine with purple eyes.",
            repository=repository,
        )
        noun = repository.get_entity("Angi")
        description = repository.get_entity("Small pink canine with purple eyes.")
        relations = repository.list_relations()
        classes = repository.list_entity_classes()

    assert result["noun_entity_id"] == repeated["noun_entity_id"]
    assert noun is not None and noun["entity_class"] == "MISC.Noun"
    assert description is not None and description["entity_class"] == "MISC.Description"
    assert not any(class_row["name"] == "Noun" for class_row in classes)
    assert any(
        relation["predicate"] == "describes"
        and relation["subject_entity_id"] == description["id"]
        and relation["object_entity_id"] == noun["id"]
        for relation in relations
    )


def test_character_guidance_adds_noun_type_to_an_existing_identity() -> None:
    """Reuse a same-name identity while asserting its Noun role for vision."""
    with tempfile.TemporaryDirectory() as directory:
        repository = KnowledgeRepository(db_path=Path(directory) / "knowledge.db")
        source_id = repository.upsert_source(
            SourceDTO(source_type="memory", path="memory/people", title="People"),
        )
        existing_id = repository.upsert_entity(
            EntityDTO(
                source_id=source_id,
                entity_class="PERSON",
                canonical_name="Yoi",
                description="Known person.",
            ),
        )

        result = project_character_guidance(
            name="Yoi",
            description="Adult man with rectangular glasses.",
            repository=repository,
        )
        assertions = repository.list_entity_type_assertions(entity_id=existing_id)

    assert result["noun_entity_id"] == existing_id
    assert any(assertion["entity_class"] == "MISC.Noun" for assertion in assertions)


def test_set_character_command_returns_graph_projection() -> None:
    """Keep character configuration and knowledge projection in one CLI operation."""
    args = Namespace(
        command="set-picture-guidance",
        section="characters",
        name="Mia",
        description="Blue canine.",
        json=False,
    )
    with (
        patch(
            "brain.presentation.actions.pictures.command_picture_guidance.set_picture_guidance_entry",
            return_value={"section": "characters", "name": "Mia", "description": "Blue canine."},
        ),
        patch(
            "brain.presentation.actions.pictures.command_picture_guidance.project_character_guidance",
            return_value={"noun_entity_id": 4, "description_entity_id": 5},
        ) as projector,
    ):
        result = handle(args)

    assert result == 0
    assert args.json_payload["graph"]["noun_entity_id"] == 4
    projector.assert_called_once_with(name="Mia", description="Blue canine.")


def test_picture_description_projects_named_characters_tags_and_current_relations() -> None:
    """Retain img2text subjects and explicit semantic tags as source-owned graph relations."""
    guidance = PictureGuidanceConfigDTO(
        characters={"Angi": "Pink canine.", "Mia": "Blue canine.", "Yoi": "Adult man."},
        tags={"familiarity": "Relaxed interaction.", "love": "Visible caring contact."},
    )
    record = SimpleNamespace(
        id="picture-1",
        active=True,
        filename="team.png",
        relative_path="code_team/team.png",
        description="**Subjects:** Yoi and Angi.\n**Semantic Tags:** familiarity, love.",
    )
    with tempfile.TemporaryDirectory() as directory:
        repository = KnowledgeRepository(db_path=Path(directory) / "knowledge.db")
        first = project_picture_description(record=record, guidance=guidance, repository=repository)
        record.description = "**Subjects:** Angi.\n**Semantic Tags:** familiarity."
        second = project_picture_description(record=record, guidance=guidance, repository=repository)
        relations = repository.list_relations()
        source = repository.get_source_by_path("pictures/code_team/team.png")
        angi = repository.get_entity("Angi")
        yoi = repository.get_entity("Yoi")
        picture = repository.get_entity("code_team/team.png")

    assert first["characters"] == ["Angi", "Yoi"]
    assert first["tags"] == ["familiarity", "love"]
    assert second["characters"] == ["Angi"]
    assert second["tags"] == ["familiarity"]
    assert source is not None and source["source_type"] == "picture"
    assert angi is not None and yoi is not None and picture is not None
    assert any(
        relation["predicate"] == "depicts"
        and relation["subject_entity_id"] == picture["id"]
        and relation["object_entity_id"] == angi["id"]
        for relation in relations
    )
    assert not any(
        relation["predicate"] == "depicts" and relation["object_entity_id"] == yoi["id"]
        for relation in relations
    )
