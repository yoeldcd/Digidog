# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Contracts for explicit avatar emotion and reaction registries."""

import random
from pathlib import Path

from brain.presentation.avatar.interactivity import emotions, reactions
from brain.infrastructure.avatar.configuration.avatar_config_dtos import AvatarConfigDTO
from brain.presentation.avatar.interactivity.emotions import EMOTION_EMOJIS, emotion_emoji
from brain.presentation.avatar.interactivity.reactions import (
    REACTION_PHRASES,
    ReactionPhraseBag,
    load_avatar_interaction_config,
)


def test_all_one_hundred_emotions_are_declared_in_one_literal_registry() -> None:
    assert len(EMOTION_EMOJIS) == 100
    assert all(name and emoji for name, emoji in EMOTION_EMOJIS.items())
    assert emotion_emoji("debugging") == "🐛"
    assert emotion_emoji("unknown-emotion") == EMOTION_EMOJIS["happy"]
    source = Path(emotions.__file__).read_text(encoding="utf-8")
    assert "_EMOJI_CYCLE" not in source
    assert "EMOTION_EMOJIS.update" not in source


def test_reactions_draw_complete_reviewed_phrases_without_cross_product() -> None:
    assert len(REACTION_PHRASES) == len(set(REACTION_PHRASES)) >= 40
    bag = ReactionPhraseBag(random.Random(7))
    cycle = [bag.draw() for _ in REACTION_PHRASES]
    assert set(cycle) == set(REACTION_PHRASES)
    assert all(phrase[-1] in ".!?" for phrase in cycle)
    source = Path(reactions.__file__).read_text(encoding="utf-8")
    assert "_OPENERS" not in source
    assert "_CLOSERS" not in source
    assert "for opener" not in source

def test_avatar_interaction_config_validates_quota_and_reaction_entries() -> None:
    """Configuration exposes typed reactions and the strict boolean flag."""
    config = AvatarConfigDTO.model_validate(
        {
            "ignore_quota_state": True,
            "reactions": [
                {"message": "Sentí tus dos clics", "animation": "animation_1.gif"},
            ],
        }
    )

    ignore_quota, configured = load_avatar_interaction_config(config)

    assert ignore_quota is True
    assert len(configured) == 1
    assert configured[0].message == "Sentí tus dos clics"
    assert configured[0].animation == "animation_1.gif"
    bag = ReactionPhraseBag(random.Random(7), configured)
    assert bag.draw_reaction() == configured[0]
