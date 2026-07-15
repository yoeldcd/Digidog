"""Non-repeating, identity-neutral avatar click reactions."""

from __future__ import annotations

import random


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


class ReactionPhraseBag:
    """Shuffle complete reviewed phrases and consume each once per cycle."""

    def __init__(self, randomizer: random.Random | None = None) -> None:
        self.randomizer = randomizer or random.Random()
        self._remaining: list[str] = []

    def draw(self) -> str:
        """Return one phrase without repetition until the current cycle ends."""
        if not self._remaining:
            self._remaining = list(REACTION_PHRASES)
            self.randomizer.shuffle(self._remaining)
        return self._remaining.pop()
