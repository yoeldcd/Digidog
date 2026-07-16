# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Contracts for reviewed, best-effort narrated CLI events."""

from argparse import Namespace
from unittest.mock import patch

from brain.infrastructure.voice.daemon import cohere_signal_presentation, cohere_signal_text
from brain.infrastructure.voice.signals import VoiceSignalService, natural_timestamp
from brain.presentation.router.services.narration_policy import CommandNarration


def test_reviewed_template_is_dispatched_for_llm_refinement() -> None:
    narration = CommandNarration("no-speak", "Éxito: Registré {TASK_ID}: {TITLE}.", True)
    with patch("brain.infrastructure.voice.signals.VoiceService.present") as speak:
        VoiceSignalService().emit_reviewed(
            command="add-task",
            phase="output",
            narration=narration,
            args=Namespace(task_id="t42", title="Revisar interfaz"),
            output="[SUCCESS] Added task #t42: Revisar interfaz",
        )
    call = speak.call_args.kwargs
    assert "Plantilla aprobada:" in call["text"]
    assert '"task_id": "t42"' in call["text"]
    assert call["signal_key"] == "reviewed-template:add-task:output"
    assert "t42" in call["display_text"]
    assert "Plantilla aprobada" not in call["display_text"]
    assert "Argumentos reales" not in call["display_text"]


def test_template_without_refinement_speaks_selected_sentence_only() -> None:
    narration = CommandNarration("no-speak", "Éxito: Guardé el dato. | Error: Falló.", False)
    with patch("brain.infrastructure.voice.signals.VoiceService.present") as speak:
        VoiceSignalService().emit_reviewed(
            command="set-memory-entry",
            phase="output",
            narration=narration,
            args=Namespace(),
        )
    assert speak.call_args.kwargs["text"] == "Guardé el dato."
    assert speak.call_args.kwargs["display_text"] == "Guardé el dato."
    assert speak.call_args.kwargs["signal_key"] == ""


def test_signal_retries_once_after_cold_start_race() -> None:
    with (
        patch("brain.infrastructure.voice.signals.time.sleep"),
        patch("brain.infrastructure.voice.signals.VoiceService.present", side_effect=[RuntimeError("starting"), None]) as speak,
    ):
        VoiceSignalService.emit("Señal recuperada", signal_key="task-added")
    assert speak.call_count == 2
    assert speak.call_args.kwargs["display_text"] == "Señal recuperada"


def test_timestamp_uses_natural_spanish_time() -> None:
    assert natural_timestamp("11-07-2026 09:05 am") == "11 de julio de 2026 9 y 5 de la mañana"
    assert natural_timestamp("11-07-2026 08:00 pm") == "11 de julio de 2026 8 en punto de la noche"


def test_daemon_coheres_signal_with_current_text_model() -> None:
    request = {"text": "Borrador factual", "signalKey": "reviewed-template:query:output"}
    with patch("brain.application.querying.llm.request_query_json", return_value={"text": "Una idea cohesiva en español."}) as llm:
        assert cohere_signal_text(request) == "Una idea cohesiva en español."
    prompt = llm.call_args.kwargs["system_prompt"]
    assert "Plantilla aprobada" in prompt
    assert "no uses palabras" in prompt


def test_daemon_keeps_fallback_when_llm_is_unavailable() -> None:
    request = {
        "text": (
            "Comando: complete-work\n"
            "Fase: output\n"
            "Plantilla aprobada: Termin\u00e9 la tarea {TASK_ID}.\n"
            "Fallback seguro: Termin\u00e9 la tarea t27.\n"
            'Argumentos reales: {"task_id": "t27"}\n'
            "Salida real: [SUCCESS]"
        ),
        "signalKey": "reviewed-template:complete-work:output",
    }
    with patch("brain.application.querying.llm.request_query_json", side_effect=RuntimeError("offline")):
        result = cohere_signal_text(request)
    assert result == "Termin\u00e9 la tarea t27."
    assert "Argumentos reales" not in result


def test_daemon_rejects_llm_output_that_leaks_technical_envelope() -> None:
    request = {
        "text": "Fallback seguro: Termin\u00e9 la tarea t27.\nArgumentos reales: {}",
        "signalKey": "reviewed-template:complete-work:output",
    }
    leaked = "comando: complete-work\nargumentos reales: {}"
    with patch("brain.application.querying.llm.request_query_json", return_value={"text": leaked}):
        assert cohere_signal_text(request) == "Termin\u00e9 la tarea t27."


def test_daemon_rejects_refinement_that_genericizes_the_approved_action() -> None:
    request = {
        "text": (
            "Comando: delete-task\n"
            "Fase: output\n"
            "Plantilla aprobada: No pude eliminar la tarea {TASK_ID} debido al error: {cause}.\n"
            "Fallback seguro: No pude eliminar la tarea t278 porque sigue en estado WORKING.\n"
            'Argumentos reales: {"task_id": "t278"}\n'
            "Salida real: Error"
        ),
        "signalKey": "reviewed-template:delete-task:output",
    }
    genericized = "No pude completar la tarea t278 porque sigue en estado WORKING."
    with patch("brain.application.querying.llm.request_query_json", return_value={"text": genericized}):
        assert cohere_signal_text(request) == request["text"].splitlines()[3].removeprefix("Fallback seguro: ")


def test_daemon_replaces_private_signal_envelope_for_visual_presentation() -> None:
    request = {
        "text": "Fallback seguro: Termin\u00e9 la tarea t27.\nArgumentos reales: {}",
        "displayText": "Comando: complete-work\nArgumentos reales: {}",
        "signalKey": "reviewed-template:complete-work:output",
    }
    with patch("brain.application.querying.llm.request_query_json", side_effect=RuntimeError("offline")):
        cohere_signal_presentation(request)
    assert request["text"] == "Termin\u00e9 la tarea t27."
    assert request["displayText"] == "Termin\u00e9 la tarea t27."
