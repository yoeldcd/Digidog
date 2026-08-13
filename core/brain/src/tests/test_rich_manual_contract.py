"""Contract tests for rich Brain command manuals and public schemas."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from brain.infrastructure.runtime.paths import get_workspace_root
from brain.presentation.commands.memory.command_get_memory_entry import (
    SCHEMA as GET_MEMORY_ENTRY_SCHEMA,
)
from brain.presentation.commands.models import CommandSchema, PayloadSchema, SchemaField
from brain.presentation.commands.utilities.command_apply_patch import (
    SCHEMA as APPLY_PATCH_SCHEMA,
)
from brain.presentation.commands.utilities.command_code_quality import (
    SCHEMA as CODE_QUALITY_SCHEMA,
)
from brain.presentation.parser.services.argument_parser_service import (
    build_argument_parser,
)
from brain.presentation.views.help.rendering import (
    get_command_help_text,
    render_manual_sections,
)


def _schema() -> CommandSchema:
    """Build one minimal command schema used by rendering parity tests.

    Args:
        No arguments are accepted.

    Returns:
        CommandSchema: Immutable schema containing every manual section.
    """

    return CommandSchema(
        name="manual-demo",
        help="Compact summary.",
        description="Detailed command description.",
        stdin=("Reads JSON from stdin.",),
        examples=("py {LOCAL_BRAIN_SCRIPT} manual-demo --json",),
        output=("Prints a result object.",),
        exit_codes=("0 success; 2 invalid input.",),
        safeguards=("Requires explicit confirmation.",),
        notes=("Safe for automation.",),
        input_schemas=(
            PayloadSchema(
                name="Request",
                media_type="application/json",
                description="Input payload.",
                fields=(SchemaField("query", "string", True, "Search text."),),
                example=(
                    "py {LOCAL_BRAIN_SCRIPT} manual-demo --json",
                    '{"query":"demo"}',
                ),
            ),
        ),
        output_schemas=(
            PayloadSchema(
                name="Response",
                media_type="application/json",
                fields=(SchemaField("ok", "boolean", True, "Success flag."),),
                example=('{"ok":true}',),
            ),
        ),
    )


def test_focused_help_renders_all_rich_manual_sections() -> None:
    """Render every canonical manual section.

    Args:
        No arguments are accepted.

    Returns:
        None: Assertions complete when every section is present.
    """
    text = render_manual_sections(_schema())

    for section in (
        "Description",
        "Stdin",
        "Examples",
        "Output",
        "Exit codes",
        "Safeguards",
        "Notes",
        "Input schemas",
        "Output schemas",
    ):
        assert f"{section}:" in text


def test_argparse_help_matches_focused_help_sections(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep argparse and focused help aligned and materialized.

    Args:
        capsys: Pytest output capture fixture.

    Returns:
        None: Assertions complete when both help routes match.
    """
    schema = _schema()
    parser = build_argument_parser([SimpleNamespace(SCHEMA=schema)])

    with pytest.raises(SystemExit) as raised:
        parser.parse_args([schema.name, "-h"])

    assert raised.value.code == 0

    argparse_help = capsys.readouterr().out
    focused = render_manual_sections(schema)

    for section in (
        "Description",
        "Stdin",
        "Examples",
        "Output",
        "Exit codes",
        "Safeguards",
        "Notes",
    ):
        assert f"{section}:" in argparse_help
        assert f"{section}:" in focused

    assert schema.description in argparse_help
    expected_script = (
        (get_workspace_root() / "$agent" / "scripts" / "brain.py").resolve().as_posix()
    )
    assert f"py '{expected_script}' manual-demo --json" in argparse_help
    assert "{LOCAL_BRAIN_SCRIPT}" not in argparse_help
    assert "{LOCAL_BRAIN_SCRIPT}" not in focused
    assert "query (string, required) - Search text." in argparse_help


def test_apply_patch_help_exposes_structured_input_and_output_contracts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep both help routes explicit about patch payload names and fields.

    Args:
        capsys: Pytest output capture fixture.

    Returns:
        None: Assertions complete when all structured fields are rendered.
    """
    parser = build_argument_parser([SimpleNamespace(SCHEMA=APPLY_PATCH_SCHEMA)])

    with pytest.raises(SystemExit) as raised:
        parser.parse_args([APPLY_PATCH_SCHEMA.name, "-h"])

    assert raised.value.code == 0
    argparse_help = capsys.readouterr().out
    focused_help = render_manual_sections(APPLY_PATCH_SCHEMA)

    for rendered in (argparse_help, focused_help):
        assert "json_patch_request" in rendered
        assert "native_patch_text" in rendered
        assert "edits" in rendered
        assert "expectedOccurrences" in rendered
        assert "allowEmptyResult" in rendered
        assert "patch_success" in rendered
        assert "patch_error" in rendered
        assert "file_result" in rendered
        assert "rollback" in rendered
        assert "cleanup" in rendered
        assert "recoveryArtifacts" in rendered


def test_registered_help_materializes_the_local_brain_script() -> None:
    """Render executable examples instead of leaking the storage placeholder.

    Args:
        No arguments are accepted.

    Returns:
        None: Assertions complete when the path is materialized.
    """
    rendered = get_command_help_text(APPLY_PATCH_SCHEMA.name, color=False)

    assert "{LOCAL_BRAIN_SCRIPT}" not in rendered
    expected_script = (
        (get_workspace_root() / "$agent" / "scripts" / "brain.py").resolve().as_posix()
    )
    assert f"py '{expected_script}' apply-patch" in rendered


@pytest.mark.parametrize(
    ("schema", "expected_schema_names", "expected_fields"),
    (
        (
            CODE_QUALITY_SCHEMA,
            (
                "request-schema",
                "result-schema",
                "format-schema",
                "error-schema",
                "config-schema",
                "model-schema",
            ),
            ("default_evaluator_id", "exit_code", "blocks_aggregate", "summary"),
        ),
        (
            GET_MEMORY_ENTRY_SCHEMA,
            ("entry-raw", "entry-envelope", "directory", "error"),
            ("preamble", "content", "entries", "error"),
        ),
    ),
)
def test_schema_aware_commands_render_their_structured_contracts(
    schema: CommandSchema,
    expected_schema_names: tuple[str, ...],
    expected_fields: tuple[str, ...],
) -> None:
    """Keep schema-aware manuals explicit about their payload variants.

    Args:
        schema: Command schema whose manual is rendered.
        expected_schema_names: Schema labels required in the manual.
        expected_fields: Field labels required in the manual.

    Returns:
        None: Assertions complete when all schema details are rendered.
    """
    rendered = render_manual_sections(schema)

    for schema_name in expected_schema_names:
        assert schema_name in rendered

    for field_name in expected_fields:
        assert field_name in rendered


def test_code_quality_manual_matches_live_public_contract() -> None:
    """Verify the rendered code-quality manual exposes live schemas and gates.

    Args:
        No arguments are accepted.

    Returns:
        None: Assertions complete when manual rendering is authoritative.
    """
    rendered = get_command_help_text(CODE_QUALITY_SCHEMA.name, color=False)
    expected_script = (
        (get_workspace_root() / "$agent" / "scripts" / "brain.py").resolve().as_posix()
    )

    assert f"py '{expected_script}' code-quality" in rendered
    assert "{LOCAL_BRAIN_SCRIPT}" not in rendered
    assert "stdin JSON" in rendered
    assert "blocks_aggregate" in rendered
    assert "REQ-01-DIGEST" in rendered
    assert "JS-SYNTAX" in rendered
    assert "TS-SYNTAX" in rendered
    assert "PY-SYNTAX" in rendered
    assert "JSON-SYNTAX" in rendered
    assert "MD-SYNTAX" in rendered
    assert "PS-SYNTAX" in rendered

    for section in (
        "Description",
        "Stdin",
        "Examples",
        "Output",
        "Exit codes",
        "Safeguards",
        "Notes",
        "Input schemas",
        "Output schemas",
    ):
        assert f"{section}:" in rendered


def test_code_quality_examples_are_direct_shell_invocations() -> None:
    """Keep every documented example on the supported direct CLI boundary.

    Args:
        No arguments are accepted.

    Returns:
        None: Assertions complete when examples are path-based and parseable.
    """

    for example in CODE_QUALITY_SCHEMA.examples:
        assert example.startswith("py {LOCAL_BRAIN_SCRIPT} code-quality")
        assert "stdin" not in example.lower()
        assert "json" in example
