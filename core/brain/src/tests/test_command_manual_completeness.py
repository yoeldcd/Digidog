"""Completeness contract for every registered Brain command manual."""

from __future__ import annotations

import shlex
from collections.abc import Iterable

import pytest
from brain.presentation.commands.models import CommandSchema, SubcommandSchema
from brain.presentation.commands.registry import COMMAND_MODULES
from brain.presentation.parser.services.argument_parser_service import (
    build_argument_parser,
)

ManualSchema = CommandSchema | SubcommandSchema


def _registered_manuals() -> Iterable[tuple[str, ManualSchema]]:
    """Yield stable labels and schemas for commands and nested subcommands."""
    for module in COMMAND_MODULES:
        command = module.SCHEMA
        yield command.name, command

        for subcommand in command.subcommands:
            yield f"{command.name} {subcommand.name}", subcommand


@pytest.mark.parametrize(("label", "schema"), tuple(_registered_manuals()))
def test_every_registered_command_has_a_complete_manual(
    label: str,
    schema: ManualSchema,
) -> None:
    """Reject registered commands whose operational manual is incomplete."""
    assert schema.help.strip(), f"{label}: missing help summary"
    assert schema.description.strip(), f"{label}: missing description"
    assert schema.examples, f"{label}: missing examples"
    assert schema.output, f"{label}: missing output contract"
    assert schema.exit_codes, f"{label}: missing exit-code contract"
    assert schema.safeguards, f"{label}: missing safeguards"
    assert schema.notes, f"{label}: missing notes"

    for example in schema.examples:
        assert "{LOCAL_BRAIN_SCRIPT}" in example, (
            f"{label}: examples must use the stable local Brain placeholder"
        )
        assert example.startswith("py {LOCAL_BRAIN_SCRIPT} "), (
            f"{label}: examples must use canonical launcher prefix"
        )


@pytest.mark.parametrize(("label", "schema"), tuple(_registered_manuals()))
def test_registered_manuals_do_not_contain_known_generic_filler(
    label: str,
    schema: ManualSchema,
) -> None:
    """Reject boilerplate that does not explain the individual command."""
    rendered_fields = (
        schema.description,
        *schema.examples,
        *schema.output,
        *schema.safeguards,
        *schema.notes,
    )
    rendered = "\n".join(rendered_fields).casefold()

    assert "execute the " not in rendered, f"{label}: generic execution filler"
    assert "report its result" not in rendered, f"{label}: generic result filler"
    assert "--help" not in "\n".join(schema.examples), (
        f"{label}: help is not a usage example"
    )


def _example_arguments(example: str) -> list[str]:
    """Convert one direct shell example into arguments accepted by Brain."""
    tokens = shlex.split(example, posix=True)
    assert tokens[:2] == ["py", "{LOCAL_BRAIN_SCRIPT}"]

    command_arguments = tokens[2:]
    for shell_operator in ("<", ">", "|", ">>"):
        if shell_operator in command_arguments:
            command_arguments = command_arguments[
                : command_arguments.index(shell_operator)
            ]

    return command_arguments


@pytest.mark.parametrize(("label", "schema"), tuple(_registered_manuals()))
def test_every_documented_example_matches_the_registered_parser(
    label: str,
    schema: ManualSchema,
) -> None:
    """Reject examples that use unknown flags or omit required arguments."""
    parser = build_argument_parser(COMMAND_MODULES)

    for example in schema.examples:
        try:
            parser.parse_args(_example_arguments(example))
        except SystemExit as error:
            pytest.fail(f"{label}: invalid example ({error.code}): {example}")
