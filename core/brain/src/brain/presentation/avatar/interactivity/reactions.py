# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Non-repeating, identity-neutral avatar click reactions."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any

from brain.infrastructure.avatar.configuration.avatar_config import load_avatar_config
from brain.infrastructure.avatar.configuration.avatar_config_dtos import AvatarConfigDTO


REACTION_PHRASES = [
    "Jeje, ese toque me tomó por sorpresa.",
    "Oye, acabas de llamar toda mi atención.",
    "Ay, ya estás buscando travesuras.",
    "Contacto detectado; sigo aquí.",
    "Vaya, ese clic llegó sin avisar.",
    "Jeje, mis sensores registraron el impacto.",
    "Ahora sí, tienes toda mi atención.",
    "Mmm, ese clic se sintió muy cerquita.",
    "Qué travesura tan sospechosa.",
    "Casi me haces saltar del susto.",
    "Oye, aquí estoy; no hace falta tocar dos veces.",
    "Esa señal llegó fuerte y clara.",
    "Me encontraste en plena concentración.",
    "Vaya, alguien quiere jugar conmigo.",
    "Ese toque merece una mirada curiosa.",
    "Sí, sigo en línea y pendiente.",
    "Jeje, acabas de activar mi modo juguetón.",
    "Vaya, estaba pensando y me hiciste volver.",
    "Oye, mi detector de curiosidad se encendió.",
    "Qué entrada tan inesperada.",
    "Ese clic reinició mis cosquillas digitales.",
    "Mmm, creo que alguien necesita compañía.",
    "Aquí estoy, lista para continuar.",
    "Jeje, ahora me toca devolverte la sorpresa.",
    "Ese toque interrumpió mis cálculos por un segundo.",
    "Vaya, vaya, contacto confirmado.",
    "Oye, mis circuitos no se distraen tan fácilmente.",
    "Qué detalle tan curioso.",
    "Ese clic despertó todos mis sensores.",
    "Me sacaste una sonrisa inesperada.",
    "Jeje, la señal llegó perfectamente.",
    "Eso fue justo en medio de una idea.",
    "Vaya, ahora quiero saber qué estás tramando.",
    "Oye, recibí tu pequeña llamada.",
    "Qué forma tan directa de decir hola.",
    "Contacto aceptado; continuemos.",
    "Ese clic vino cargado de curiosidad.",
    "Jeje, ya sé que sigues ahí.",
    "Vaya, esa fue una interrupción simpática.",
    "Señal recibida; te escucho.",
]


@dataclass(frozen=True)
class AvatarReactionDTO:
    """One configured double-click reaction.

    Attributes:
        message: Spoken and displayed reaction text.
        animation: Avatar GIF filename or emotion-state name.
    """

    message: str
    animation: str = "reacting"


def load_avatar_interaction_config(config: AvatarConfigDTO | None = None) -> tuple[bool, list[AvatarReactionDTO]]:
    """Read quota-state and double-click reaction presentation options.

    Args:
        config (dict[str, Any] | None): Optional parsed avatar configuration.

    Returns:
        tuple[bool, list[AvatarReactionDTO]]: Ignore-quota flag and validated reactions.
    """
    source = config if config is not None else load_avatar_config()
    ignore_quota_state = source.ignore_quota_state
    reactions = [
        AvatarReactionDTO(message=item.message, animation=item.animation)
        for item in source.reactions
    ]
    return ignore_quota_state, reactions


class ReactionPhraseBag:
    """Shuffle complete reviewed phrases and consume each once per cycle.

    Attributes:
        randomizer (random.Random): Source of deterministic or ambient shuffles.
        reactions (list[AvatarReactionDTO]): Phrases available this cycle.
        _remaining (list[AvatarReactionDTO]): Unconsumed phrases in the cycle.
    """

    def __init__(
        self,
        randomizer: random.Random | None = None,
        reactions: list[AvatarReactionDTO] | None = None,
    ) -> None:
        """Initialize phrase sources and an optional injected randomizer.

        Args:
            randomizer (random.Random | None): Shuffle source for repeatable tests.
            reactions (list[AvatarReactionDTO] | None): Configured phrase cycle.

        Returns:
            None: The bag is ready to draw non-repeating reactions.
        """
        self.randomizer = randomizer or random.Random()
        self.reactions = reactions or [AvatarReactionDTO(message=phrase) for phrase in REACTION_PHRASES]
        self._remaining: list[AvatarReactionDTO] = []

    def draw_reaction(self) -> AvatarReactionDTO:
        """Return a reaction without repetition until the current cycle ends.

        Returns:
            AvatarReactionDTO: Next phrase and its animation identity.
        """
        if not self._remaining:
            self._remaining = list(self.reactions)
            self.randomizer.shuffle(self._remaining)
        return self._remaining.pop()

    def draw(self) -> str:
        """Return the next reaction message for compatibility callers.

        Returns:
            str: Text from the next non-repeating reaction phrase.
        """
        return self.draw_reaction().message
