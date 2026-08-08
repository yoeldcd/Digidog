# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Contracts for reviewed, best-effort narrated CLI events."""

from argparse import Namespace
from unittest.mock import patch

from brain.infrastructure.voice.contracts.avatar_speak_request import AvatarSpeakRequest
from brain.infrastructure.voice.daemon.daemon import cohere_signal_presentation, cohere_signal_text
from brain.infrastructure.voice.messaging.voice_signals import VoiceSignalService, _render_narration_table, natural_timestamp
from brain.presentation.router.services.command_show_policy import CommandShowPolicy
from brain.presentation.router.services.narration_policy import CommandNarration


def test_visual_table_omits_a_redundant_common_source() -> None:
    args = Namespace(
        narration_table_columns=['source', 'domain', 'content'],
        narration_table_rows=[
            {'source': 'backlog', 'domain': 'core.ui', 'content': 't1'},
            {'source': 'backlog', 'domain': 'core.voice', 'content': 't2'},
        ],
    )
    table = _render_narration_table(args)
    assert table.startswith('| domain | content |')
    assert 'source' not in table


def test_visual_table_keeps_source_when_rows_mix_origins() -> None:
    args = Namespace(
        narration_table_columns=['source', 'domain', 'content'],
        narration_table_rows=[
            {'source': 'records', 'domain': 'records', 'content': 'policy'},
            {'source': 'logs', 'domain': 'core.ui', 'content': 'change'},
        ],
    )
    assert _render_narration_table(args).startswith('| source | domain | content |')


def test_refinement_preserves_semantic_table_without_source_column() -> None:
    request = {
        'text': 'reviewed draft',
        'displayText': 'Resumen.\n\n| estado | tarea |\n| --- | --- |\n| 🛠️ `WORKING` | `t1` |',
        'signalKey': 'reviewed-template:show-backlog:output',
    }
    with patch('brain.infrastructure.voice.daemon.daemon.cohere_signal_text', return_value='Resumen refinado.'):
        cohere_signal_presentation(request)
    assert request['text'] == 'Resumen refinado.'
    assert '| estado | tarea |' in request['displayText']


def test_reviewed_template_is_dispatched_for_llm_refinement() -> None:
    narration = CommandNarration("no-speak", "Éxito: Registré {TASK_ID}: {TITLE}.", True)
    with patch("brain.infrastructure.voice.messaging.voice_signals.VoiceService.present") as speak:
        VoiceSignalService().emit_reviewed(
            command="add-task",
            phase="output",
            narration=narration,
            args=Namespace(task_id="t42", title="Revisar interfaz"),
            output="[SUCCESS] Added task #t42: Revisar interfaz",
        )
    request = speak.call_args.args[0]
    assert isinstance(request, AvatarSpeakRequest)
    assert "Plantilla aprobada:" in request.text
    assert '"task_id": "t42"' in request.text
    assert request.signal_key == "reviewed-template:add-task:output"
    assert "t42" in request.display_text
    assert "Plantilla aprobada" not in request.display_text
    assert "Argumentos reales" not in request.display_text


def test_template_without_refinement_speaks_selected_sentence_only() -> None:
    narration = CommandNarration("no-speak", "Éxito: Guardé el dato. | Error: Falló.", False)
    with patch("brain.infrastructure.voice.messaging.voice_signals.VoiceService.present") as speak:
        VoiceSignalService().emit_reviewed(
            command="set-memory-entry",
            phase="output",
            narration=narration,
            args=Namespace(),
        )
    request = speak.call_args.args[0]
    assert request == AvatarSpeakRequest(
        text="Guardé el dato.",
        display_text="Guardé el dato.",
        emotion="focused",
        source_command="set-memory-entry",
        source_phase="output",
    )


def test_signal_retries_once_after_cold_start_race() -> None:
    with (
        patch("brain.infrastructure.voice.messaging.voice_signals.time.sleep"),
        patch("brain.infrastructure.voice.messaging.voice_signals.VoiceService.present", side_effect=[RuntimeError("starting"), None]) as speak,
    ):
        VoiceSignalService.emit("Señal recuperada", signal_key="task-added")
    assert speak.call_count == 2
    assert speak.call_args.args[0].display_text == "Señal recuperada"


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


def test_signal_maps_every_configured_presentation_field_into_request() -> None:
    """Configured command presentation fields cross the signal boundary unchanged."""
    policy = CommandShowPolicy(show_message=False, speak_message=False, hiden_on_muted=True, level="important", pre_processor="Resume: {OUTPUT}", animation="celebrating")
    with patch("brain.infrastructure.voice.messaging.voice_signals.VoiceService.present") as present:
        VoiceSignalService.emit("Resultado", emotion="focused", show_policy=policy)
    request = present.call_args.args[0]
    assert request == AvatarSpeakRequest(text="Resultado", display_text="Resultado", emotion="celebrating", show_message=False, speak_message=False, hide_when_muted=True, message_level="important", pre_processor="Resume: {OUTPUT}")