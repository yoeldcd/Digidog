# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Argument parser construction service for Brain CLI command schemas.

Constructs top-level and subcommand argparse objects from declarative schemas.
Enforces common flags such as --json and --authority across all subcommands.
"""

from __future__ import annotations

import argparse
from types import ModuleType
from typing import Final, NoReturn

from brain.presentation.commands.models import ArgumentSchema, CommandSchema
from brain.presentation.views.help.rendering import render_manual_sections

ARGUMENT_ERROR_MESSAGE: Final[str] = "Invalid command arguments."

JSON_ARGUMENT = ArgumentSchema(
    flags=["-j", "--json"],
    action="store_true",
    help="Print machine-readable JSON output.",
)

AUTHORITY_ARGUMENT = ArgumentSchema(
    flags=["--authority"],
    type="str",
    default="orchestrator",
    help="Define authority string for command execution control.",
)


class _SafeArgumentParser(argparse.ArgumentParser):
    """Parse CLI arguments without echoing rejected values in error output."""

    def error(self, _message: str) -> NoReturn:
        """Exit with one generic parse error that does not include input values.

        Args:
            _message: Argparse's detailed diagnostic, intentionally discarded.

        Returns:
            NoReturn: This method always terminates through argparse.
        """

        self.exit(2, f"Error: {ARGUMENT_ERROR_MESSAGE}\n")


def build_argument_parser(command_modules: list[ModuleType]) -> argparse.ArgumentParser:
    """Build an ``argparse`` parser from declarative command schemas.

    Iterates over supplied command modules, instantiates top-level subparsers,
    and attaches standard common flags (--json, --authority) to each command.

    Args:
        command_modules: Modules exposing ``SCHEMA`` objects.

    Returns:
        argparse.ArgumentParser: Configured top-level command parser.
    """
    parser = _SafeArgumentParser(
        description="Manage memory store domains.", add_help=True
    )

    parser.add_argument(
        "--no-speak",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    subparsers = parser.add_subparsers(
        dest="command",
        parser_class=_SafeArgumentParser,
    )

    # Iteration: bind each registered command module to the CLI subparsers

    for command_module in command_modules:
        command_schema: CommandSchema = command_module.SCHEMA

        command_parser = subparsers.add_parser(
            command_schema.name,
            aliases=command_schema.aliases,
            help=command_schema.help,
            description=_manual_description(command_schema),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        command_parser.set_defaults(command=command_schema.name)

        _bind_arguments(
            parser=command_parser, argument_schemas=command_schema.arguments
        )

        # Flag binding: attach common JSON output argument if absent

        if not _has_json_argument(argument_schemas=command_schema.arguments):
            _bind_arguments(parser=command_parser, argument_schemas=[JSON_ARGUMENT])

        # Flag binding: attach common authority argument if absent

        if not _has_authority_argument(argument_schemas=command_schema.arguments):
            _bind_arguments(
                parser=command_parser, argument_schemas=[AUTHORITY_ARGUMENT]
            )

        # Subcommand binding: process nested subcommand subparsers if declared

        if command_schema.subcommands:
            nested_subparsers = command_parser.add_subparsers(
                dest=command_schema.subcommand_dest,
                parser_class=_SafeArgumentParser,
            )

            # Iteration: bind each nested subcommand schema to the subparser

            for subcommand_schema in command_schema.subcommands:
                nested_parser = nested_subparsers.add_parser(
                    subcommand_schema.name,
                    help=subcommand_schema.help,
                    description=_manual_description(subcommand_schema),
                    formatter_class=argparse.RawDescriptionHelpFormatter,
                )

                _bind_arguments(
                    parser=nested_parser, argument_schemas=subcommand_schema.arguments
                )

    return parser


def _has_json_argument(argument_schemas: list[ArgumentSchema]) -> bool:
    """Return whether a command schema already declares the canonical JSON flag.

    Inspects argument definitions attached to a command schema to prevent duplicate
    registration of the standard -j / --json flag across CLI subcommands.

    Args:
        argument_schemas: List of argument schemas to inspect.

    Returns:
        bool: True if --json is declared; otherwise False.
    """

    return any(
        "--json" in argument_schema.flags for argument_schema in argument_schemas
    )


def _has_authority_argument(argument_schemas: list[ArgumentSchema]) -> bool:
    """Return whether a command schema already declares the canonical authority flag.

    Inspects argument definitions attached to a command schema to prevent duplicate
    registration of the standard --authority flag across CLI subcommands.

    Args:
        argument_schemas: List of argument schemas to inspect.

    Returns:
        bool: True if --authority is declared; otherwise False.
    """

    return any(
        "--authority" in argument_schema.flags for argument_schema in argument_schemas
    )


def _bind_arguments(
    parser: argparse.ArgumentParser, argument_schemas: list[ArgumentSchema]
) -> None:
    """Attach declarative argument schemas to an `argparse` parser.

    Converts domain ArgumentSchema definitions into concrete argparse parameters.
    Binds positional arguments and option flags onto the target parser instance.

    Args:
        parser: Parser instance receiving arguments.
        argument_schemas: Argument schemas to bind.

    Returns:
        None.
    """

    # Iteration: add each argument schema to the target parser

    for argument_schema in argument_schemas:
        parser.add_argument(
            *argument_schema.flags, **_argument_kwargs(argument_schema=argument_schema)
        )


def _argument_kwargs(argument_schema: ArgumentSchema) -> dict[str, object]:
    """Convert a command argument schema into `argparse.add_argument` keyword arguments.

    Maps declarative schema fields such as type names, actions, help text, and defaults
    into a dictionary of keyword parameters expected by argparse.add_argument.

    Args:
        argument_schema: Schema holding argument metadata.

    Returns:
        dict[str, object]: Keyword arguments dictionary for argparse.
    """
    kwargs: dict[str, object] = {}

    # Field check: set help text if specified

    if argument_schema.help:
        kwargs["help"] = argument_schema.help

    # Field check: set action if specified

    if argument_schema.action is not None:
        kwargs["action"] = argument_schema.action

    # Field check: convert type name to type object if specified

    if argument_schema.type is not None:
        kwargs["type"] = _argument_type(type_name=argument_schema.type)

    # Field check: set default value if specified

    if argument_schema.default is not None:
        kwargs["default"] = argument_schema.default

    # Field check: set required flag if true

    if argument_schema.required:
        kwargs["required"] = argument_schema.required

    # Field check: set nargs if specified

    if argument_schema.nargs is not None:
        kwargs["nargs"] = argument_schema.nargs

    return kwargs


def _argument_type(type_name: str) -> type:
    """Return a concrete parser type for a schema type name.

    Translates string type identifiers from declarative argument schemas into
    corresponding Python built-in callable types used for value casting.

    Args:
        type_name: Type name identifier ('int', 'float', or 'str').

    Returns:
        type: Python built-in type object (int, float, or str).
    """

    # Type resolution: map type name string to built-in type object

    if type_name == "int":
        return int

    if type_name == "float":
        return float

    return str


def _manual_description(schema: CommandSchema) -> str:
    """Render rich manual metadata for argparse's command description.

    Formats declarative manual sections into raw description text for terminal help documents.
    Strips leading whitespace to maintain clean alignment in subparser descriptions.

    Args:
        schema: Command schema containing description sections.

    Returns:
        str: Rendered manual text with leading whitespace stripped.
    """

    return render_manual_sections(schema).lstrip()
