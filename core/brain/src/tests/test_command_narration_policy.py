# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Coverage for owner-reviewed CLI narration selection and dispatch."""

from argparse import Namespace
import io
from unittest.mock import patch

from brain.presentation.router.services.command_router_service import dispatch_command
from brain.presentation.router.services.narration_policy import CommandNarration, build_narration_draft, narration_for
from brain.presentation.router.services.narration_templates import NARRATION_TEMPLATE_ROWS


def test_internal_contracts_drive_command_selection_and_start_phases() -> None:
    assert narration_for(command="write-diary", args=Namespace()) is not None
    assert narration_for("write-diary", Namespace()) is not None
    assert narration_for("set-task-status", Namespace()) is not None
    assert narration_for("task-finished", Namespace()) is not None
    assert narration_for("edit-task", Namespace()) is not None
    assert narration_for("list-profiles", Namespace()) is None
    assert narration_for("help", Namespace()) is None
    assert narration_for("get-context", Namespace()).announce_start is True
    assert narration_for("rebuild-vectorstore", Namespace()).announce_start is False


def test_narration_contracts_do_not_read_workspace_files() -> None:
    with patch("pathlib.Path.open", side_effect=AssertionError("runtime file access is forbidden")):
        narration = narration_for("get-context", Namespace())
    assert narration is not None
    assert narration.announce_start is True


def test_reviewed_aliases_share_templates() -> None:
    assert narration_for("init", Namespace()) == narration_for("wakeup", Namespace())
    assert narration_for("register-project", Namespace()) == narration_for("registre-proyect", Namespace())


def test_every_seeded_command_has_a_specific_packaged_output_contract() -> None:
    generic_fragments = ("He completado la operación", "No pude completar la operación")
    assert len(NARRATION_TEMPLATE_ROWS) == 47
    for command in NARRATION_TEMPLATE_ROWS:
        narration = narration_for(command, Namespace())
        assert narration is not None, command
        assert narration.output_template.strip(), command
        assert not any(fragment in narration.output_template for fragment in generic_fragments), command


def test_delete_task_error_names_the_rejected_operation() -> None:
    narration = narration_for("delete-task", Namespace())
    assert narration is not None
    draft = build_narration_draft(
        command="delete-task",
        template=narration.output_template,
        args=Namespace(task_id="t278"),
        output="Error: Task 't278' is WORKING.",
        succeeded=False,
        phase="output",
        cause="Task 't278' is WORKING.",
    )
    fallback = next(line for line in draft.splitlines() if line.startswith("Fallback seguro: "))
    assert "No pude eliminar la tarea t278" in fallback
    assert "completar la tarea" not in fallback


def test_seeded_failure_templates_preserve_their_command_domain() -> None:
    expected_verbs = {
        "delete-memory-entry": "eliminaba la entrada",
        "export-logs": "exportar los registros",
        "knowledge-export": "exportar mi conocimiento",
        "rebuild-vectorstore": "reconstruir mi índice vectorial",
    }
    for command, phrase in expected_verbs.items():
        narration = narration_for(command, Namespace())
        assert narration is not None
        assert phrase.casefold() in narration.output_template.casefold()


def test_draft_selects_status_and_includes_real_facts() -> None:
    narration = narration_for("set-task-status", Namespace())
    assert narration is not None
    draft = build_narration_draft(
        command="set-task-status",
        template=narration.output_template,
        args=Namespace(task_id="t77", status="WORKING"),
        output="[SUCCESS] Task 't77' is now WORKING.",
        succeeded=True,
        phase="output",
    )
    assert "Ya estoy trabajando" in draft
    assert "DONE:" not in draft
    assert '"task_id": "t77"' in draft
    assert "Fallback seguro: Ya estoy trabajando en la tarea t77" in draft


def test_complete_work_draft_contains_safe_spanish_fallback_without_payload_content() -> None:
    narration = narration_for("complete-work", Namespace())
    assert narration is not None
    draft = build_narration_draft(
        command="complete-work",
        template=narration.output_template,
        args=Namespace(
            task_id="t27",
            title="Activar recorte expl\u00edcito",
            description="A\u00f1ad\u00ed el control y la vista previa.",
            narration_log_summary="A\u00f1ad\u00ed el control y la vista previa.",
        ),
        output="[SUCCESS] t27 completed",
        phase="output",
    )
    fallback = next(line for line in draft.splitlines() if line.startswith("Fallback seguro: "))
    assert "t27" in fallback
    assert "Activar recorte expl\u00edcito" not in fallback
    assert "A\u00f1ad\u00ed el control" not in fallback
    assert "{" not in fallback
    assert "Argumentos reales" not in fallback


def test_dispatch_mirrors_output_and_emits_call_then_outcome() -> None:
    narration = CommandNarration("Voy a probar.", "Éxito: Terminé. | Error: Falló: {cause}.", True)

    def handler(_args: Namespace) -> int:
        print("resultado real")
        return 0

    with (
        patch("brain.presentation.router.services.command_router_service.get_action_handler", return_value=handler),
        patch("brain.presentation.router.services.command_router_service.narration_for", return_value=narration),
        patch("brain.presentation.router.services.command_router_service.VoiceSignalService.emit_reviewed") as emit,
        patch("sys.stdout", new_callable=io.StringIO) as output,
    ):
        assert dispatch_command(Namespace(command="demo", no_speak=False)) == 0
    assert "resultado real" in output.getvalue()
    assert [call.kwargs["phase"] for call in emit.call_args_list] == ["call", "output"]
    assert emit.call_args_list[1].kwargs["output"] == "resultado real\n"


def test_no_speak_bypasses_signals() -> None:
    def handler(_args: Namespace) -> int:
        print("silencioso")
        return 0

    with (
        patch("brain.presentation.router.services.command_router_service.get_action_handler", return_value=handler),
        patch("brain.presentation.router.services.command_router_service.VoiceSignalService.emit_reviewed") as emit,
        patch("sys.stdout", new_callable=io.StringIO) as output,
    ):
        assert dispatch_command(Namespace(command="query", no_speak=True)) == 0
    assert output.getvalue() == "silencioso\n"
    emit.assert_not_called()


def test_json_dispatch_preserves_machine_output_and_emits_narration() -> None:
    """JSON mode must not bypass automatic avatar narrations."""
    narration = CommandNarration("Voy a probar.", "Éxito: Terminé.", False)

    def handler(args: Namespace) -> int:
        args.json_payload = {"ok": True, "value": 7}
        return 0

    with (
        patch("brain.presentation.router.services.command_router_service.get_action_handler", return_value=handler),
        patch("brain.presentation.router.services.command_router_service.narration_for", return_value=narration),
        patch("brain.presentation.router.services.command_router_service.VoiceSignalService.emit_reviewed") as emit,
        patch("sys.stdout", new_callable=io.StringIO) as output,
    ):
        assert dispatch_command(Namespace(command="demo", json=True, no_speak=False)) == 0
    assert '"value": 7' in output.getvalue()
    assert [call.kwargs["phase"] for call in emit.call_args_list] == ["call", "output"]
