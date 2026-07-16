# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Argument parser construction service for Brain CLI command schemas."""

from __future__ import annotations

import argparse
from types import ModuleType
from typing import Any

from brain.presentation.commands.models import ArgumentSchema, CommandSchema


JSON_ARGUMENT = ArgumentSchema(
    flags=["-j", "--json"],
    action="store_true",
    help="Print machine-readable JSON output.",
)


def build_argument_parser(command_modules: list[ModuleType]) -> argparse.ArgumentParser:
    """Build an `argparse` parser from declarative command schema modules."""
    parser = argparse.ArgumentParser(description="Manage memory store domains.", add_help=True)
    parser.add_argument(
        "--no-speak",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    subparsers = parser.add_subparsers(dest="command")

    for command_module in command_modules:
        command_schema: CommandSchema = command_module.SCHEMA
        command_parser = subparsers.add_parser(
            command_schema.name,
            aliases=command_schema.aliases,
            help=command_schema.help,
        )
        command_parser.set_defaults(command=command_schema.name)
        _bind_arguments(parser=command_parser, argument_schemas=command_schema.arguments)
        if not _has_json_argument(argument_schemas=command_schema.arguments):
            _bind_arguments(parser=command_parser, argument_schemas=[JSON_ARGUMENT])

        if command_schema.subcommands:
            nested_subparsers = command_parser.add_subparsers(dest=command_schema.subcommand_dest)
            for subcommand_schema in command_schema.subcommands:
                nested_parser = nested_subparsers.add_parser(subcommand_schema.name, help=subcommand_schema.help)
                _bind_arguments(parser=nested_parser, argument_schemas=subcommand_schema.arguments)

    return parser


def _has_json_argument(argument_schemas: list[ArgumentSchema]) -> bool:
    """Return whether a command schema already declares the canonical JSON flag."""
    return any("--json" in argument_schema.flags for argument_schema in argument_schemas)


def _bind_arguments(parser: argparse.ArgumentParser, argument_schemas: list[ArgumentSchema]) -> None:
    """Attach declarative argument schemas to an `argparse` parser."""
    for argument_schema in argument_schemas:
        parser.add_argument(*argument_schema.flags, **_argument_kwargs(argument_schema=argument_schema))


def _argument_kwargs(argument_schema: ArgumentSchema) -> dict[str, Any]:
    """Convert a command argument schema into `argparse.add_argument` keyword arguments."""
    kwargs: dict[str, Any] = {}

    if argument_schema.help:
        kwargs["help"] = argument_schema.help
    if argument_schema.action is not None:
        kwargs["action"] = argument_schema.action
    if argument_schema.type is not None:
        kwargs["type"] = _argument_type(type_name=argument_schema.type)
    if argument_schema.default is not None:
        kwargs["default"] = argument_schema.default
    if argument_schema.required:
        kwargs["required"] = argument_schema.required
    if argument_schema.nargs is not None:
        kwargs["nargs"] = argument_schema.nargs

    return kwargs


def _argument_type(type_name: str) -> type:
    """Return a concrete parser type for a schema type name."""
    if type_name == "int":
        return int
    if type_name == "float":
        return float
    return str
