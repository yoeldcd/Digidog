# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Data transfer objects for modular memory CLI schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ArgumentSchema:
    """Normalized schema for a command line argument or option.

    Attributes:
        flags (list[str]): Argument flag names.
        help (str): User-facing usage help.
        action (str | None): ``argparse`` action name.
        type (str | None): Declarative value type name.
        default (Any): Optional default value.
        required (bool): Whether argument is mandatory.
        nargs (str | None): Optional argument-cardinality expression.
    """

    flags: list[str]
    help: str = ""
    action: str | None = None
    type: str | None = None
    default: Any = None
    required: bool = False
    nargs: str | None = None


@dataclass(slots=True)
class SubcommandSchema:
    """Normalized schema for a nested CLI subcommand.

    Attributes:
        name (str): Subcommand name.
        help (str): User-facing usage help.
        arguments (list[ArgumentSchema]): Declarative argument schemas.
    """

    name: str
    help: str
    arguments: list[ArgumentSchema] = field(default_factory=list)


@dataclass(slots=True)
class CommandSchema:
    """Normalized schema for a top-level CLI command.

    Attributes:
        name (str): Canonical command name.
        help (str): User-facing usage help.
        aliases (list[str]): Accepted alternate command names.
        arguments (list[ArgumentSchema]): Top-level argument schemas.
        subcommands (list[SubcommandSchema]): Nested command schemas.
        subcommand_dest (str | None): Namespace attribute for nested command.
        domain (str): Functional ownership domain.
    """

    name: str
    help: str
    aliases: list[str] = field(default_factory=list)
    arguments: list[ArgumentSchema] = field(default_factory=list)
    subcommands: list[SubcommandSchema] = field(default_factory=list)
    subcommand_dest: str | None = None
    domain: str = "general"
