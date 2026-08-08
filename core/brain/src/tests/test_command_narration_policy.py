# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Coverage for owner-reviewed CLI narration selection and dispatch."""

from argparse import Namespace
import io
from pathlib import Path
from unittest.mock import patch

from brain.application.backlog.models import BacklogTask
from brain.application.backlog.rendering import (
    render_task_table,
    resolve_task_reference,
    resolve_task_reference_path,
)
from brain.infrastructure.voice.narration.markdown_narration import markdown_text_for_speech
from brain.infrastructure.avatar.configuration.avatar_config_dtos import AvatarConfigDTO
from brain.presentation.actions.backlog import command_show_backlog
from brain.presentation.router.services.command_router_service import dispatch_command
from brain.presentation.router.services.command_show_policy import command_show_policy
from brain.presentation.router.services.narration_policy import (
    CommandNarration,
    build_narration_draft,
    narration_for,
    render_without_refinement,
)
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


def test_show_backlog_projects_reference_marker_without_mutating_storage() -> None:
    """CLI projection must expose the real image path while preserving stored metadata."""
    task = BacklogTask(
        task_id="t42",
        domain="core.brain",
        title="Inspect screenshot",
        description="Compare the layout.\n\n{ref_image}",
        priority="HIGH",
        status="TODO",
    )
    with patch("pathlib.Path.is_file", return_value=True):
        projected = resolve_task_reference(task=task, workspace_root=Path("workspace"))

    assert projected.description.endswith("$agent/pictures/backlog-pic-t42.png")
    assert task.description.endswith("{ref_image}")


def test_task_reference_path_returns_canonical_existing_extension() -> None:
    """The reusable resolver keeps extension selection independent of CLI projection."""
    with patch("pathlib.Path.is_file", side_effect=(False, True)):
        reference_path = resolve_task_reference_path("t42", Path("workspace"))

    assert reference_path == "$agent/pictures/backlog-pic-t42.jpg"

def test_show_backlog_narrates_only_count_and_keeps_task_table_visual() -> None:
    """Keep task details visible in Markdown while excluding them from speech."""
    tasks = [
        BacklogTask(
            task_id="t1",
            domain="core.brain",
            title="Visible task title",
            description="Visible detailed summary",
            priority="HIGH",
            status="TODO",
        ),
        BacklogTask(
            task_id="t2",
            domain="core.cli",
            title="Second visible title",
            description="Second visible summary",
            priority="MEDIUM",
            status="WORKING",
        ),
    ]
    table = render_task_table(tasks=tasks)
    narration = narration_for("show-backlog", Namespace())

    assert narration is not None
    assert narration.refine_with_llm is False
    draft = build_narration_draft(
        command="show-backlog",
        template=narration.output_template,
        args=Namespace(narration_task_count=2),
        output=table,
        succeeded=True,
        phase="output",
    )
    spoken = render_without_refinement(draft)
    assert spoken == "Tengo 2 tareas pendientes."
    assert "Visible task title" in table
    assert "Visible detailed summary" in table
    assert markdown_text_for_speech(table) == ""


def test_show_backlog_exposes_semantic_tagged_avatar_columns() -> None:
    task = BacklogTask(
        task_id='t7', domain='core.ui', title='Repair footer', description='',
        priority='HIGH', status='WORKING',
    )
    args = Namespace(task_domain=None, all=False, color=False, json=True)
    with patch.object(command_show_backlog, 'list_backlog_tasks', return_value=[task]):
        assert command_show_backlog.handle(args) == 0
    assert args.narration_table_columns == ['estado', 'dominio', 'tarea']
    assert args.narration_table_rows == [{
        'estado': '🛠️ `WORKING` · 🔴 `HIGH`',
        'dominio': 'core.ui',
        'tarea': '`t7` — Repair footer',
    }]


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


def test_json_dispatch_preserves_machine_output_and_command_narration() -> None:
    """JSON controls stdout format while the internal silence flag controls narration."""
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
    assert output.getvalue() == '{"ok":true,"value":7}\n'
    assert [call.kwargs["phase"] for call in emit.call_args_list] == ["call", "output"]

def test_configured_silent_command_bypasses_normal_and_json_narration() -> None:
    """Configured silent commands preserve outputs while emitting no voice signals."""
    def handler(args: Namespace) -> int:
        if getattr(args, "json", False):
            args.json_payload = {"ok": True}
        else:
            print("visible")
        return 0

    silent = AvatarConfigDTO(silent_commands=("quiet",))
    for args in (Namespace(command="quiet", no_speak=False), Namespace(command="quiet", json=True, no_speak=False)):
        with (
            patch("brain.presentation.router.services.command_router_service.get_action_handler", return_value=handler),
            patch("brain.presentation.router.services.command_router_service.load_avatar_config", return_value=silent),
            patch("brain.presentation.router.services.command_router_service.VoiceSignalService.emit_reviewed") as emit,
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            assert dispatch_command(args) == 0
        emit.assert_not_called()

def test_command_show_policy_normalizes_keys_and_preserves_configured_fields() -> None:
    """Hyphenated commands resolve their immutable configured presentation policy."""
    config = AvatarConfigDTO.model_validate({"commands_show_customization": {"show_backlog": {"show_message": False, "speak_message": False, "hiden_on_muted": True, "level": "important", "pre_processor": "Resume: {OUTPUT}", "animation": "celebrating"}}})
    policy = command_show_policy("show-backlog", config)
    assert policy is not None
    assert (policy.show_message, policy.speak_message, policy.hiden_on_muted) == (False, False, True)
    assert (policy.level, policy.pre_processor, policy.animation) == ("important", "Resume: {OUTPUT}", "celebrating")


def test_silent_commands_override_configured_show_customizations() -> None:
    """Authoritative silent commands suppress even an otherwise configured policy."""
    config = AvatarConfigDTO.model_validate({"silent_commands": ["show-backlog"], "commands_show_customization": {"show_backlog": {"speak_message": True}}})
    assert command_show_policy("show-backlog", config) is None