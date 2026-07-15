"""Data transfer objects for modular memory CLI schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ArgumentSchema:
    """Normalized schema for a command line argument or option."""

    flags: list[str]
    help: str = ""
    action: str | None = None
    type: str | None = None
    default: Any = None
    required: bool = False
    nargs: str | None = None


@dataclass(slots=True)
class SubcommandSchema:
    """Normalized schema for a nested CLI subcommand."""

    name: str
    help: str
    arguments: list[ArgumentSchema] = field(default_factory=list)


@dataclass(slots=True)
class CommandSchema:
    """Normalized schema for a top-level CLI command."""

    name: str
    help: str
    aliases: list[str] = field(default_factory=list)
    arguments: list[ArgumentSchema] = field(default_factory=list)
    subcommands: list[SubcommandSchema] = field(default_factory=list)
    subcommand_dest: str | None = None
    domain: str = "general"
