# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Data transfer objects for modular memory CLI schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias

DefaultValue: TypeAlias = object


@dataclass(frozen=True, slots=True)
class SchemaField:
    """Describe one field in a structured command payload.

    Attributes:
        name: Serialized field name.
        type: Human-readable value type and referenced schema name.
        required: Whether the containing payload requires the field.
        description: Constraints, defaults, and conditional availability.
    """

    name: str
    type: str
    required: bool = False
    description: str = ""


@dataclass(frozen=True, slots=True)
class PayloadSchema:
    """Describe a structured input or output payload.

    Attributes:
        name: Stable schema name referenced by other schema fields.
        media_type: MIME type consumed or emitted by the command.
        description: Purpose and structural constraints of the payload.
        fields: Ordered fields exposed by the payload.
        example: Readable serialized example, stored as display lines.
    """

    name: str
    media_type: str
    description: str = ""
    fields: tuple[SchemaField, ...] = ()
    example: tuple[str, ...] = ()


@dataclass(slots=True)
class ArgumentSchema:
    """Normalized schema for a command line argument or option.

    Attributes:
        flags (list[str]): Argument flag names.
        help (str): User-facing usage help.
        action (str | None): ``argparse`` action name.
        type (str | None): Declarative value type name.
        default (object): Optional parser default value.
        required (bool): Whether argument is mandatory.
        nargs (str | None): Optional argument-cardinality expression.
    """

    flags: list[str]
    help: str = ""
    action: str | None = None
    type: str | None = None
    default: DefaultValue = None
    required: bool = False
    nargs: str | None = None


@dataclass(slots=True)
class SubcommandSchema:
    """Normalized schema for a nested CLI subcommand.

    Attributes:
        name (str): Subcommand name.
        help (str): User-facing usage help.
        arguments (list[ArgumentSchema]): Declarative argument schemas.
        description (str): Detailed behavior and purpose.
        stdin (tuple[str, ...]): Accepted standard-input forms.
        examples (tuple[str, ...]): Direct shell usage examples.
        output (tuple[str, ...]): Human and machine-readable results.
        exit_codes (tuple[str, ...]): Process exit-code meanings.
        safeguards (tuple[str, ...]): Validation and mutation protections.
        notes (tuple[str, ...]): Additional operational details.
        input_schemas (tuple[PayloadSchema, ...]): Structured payloads accepted.
        output_schemas (tuple[PayloadSchema, ...]): Structured payloads emitted.
    """

    name: str
    help: str = ""
    arguments: list[ArgumentSchema] = field(default_factory=list)
    description: str = ""
    stdin: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    output: tuple[str, ...] = ()
    exit_codes: tuple[str, ...] = ()
    safeguards: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    input_schemas: tuple[PayloadSchema, ...] = ()
    output_schemas: tuple[PayloadSchema, ...] = ()


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
        description (str): Detailed behavior and purpose.
        stdin (tuple[str, ...]): Accepted standard-input forms.
        examples (tuple[str, ...]): Direct shell usage examples.
        output (tuple[str, ...]): Human and machine-readable results.
        exit_codes (tuple[str, ...]): Process exit-code meanings.
        safeguards (tuple[str, ...]): Validation and mutation protections.
        notes (tuple[str, ...]): Additional operational details.
        input_schemas (tuple[PayloadSchema, ...]): Structured payloads accepted.
        output_schemas (tuple[PayloadSchema, ...]): Structured payloads emitted.
    """

    name: str
    help: str
    aliases: list[str] = field(default_factory=list)
    arguments: list[ArgumentSchema] = field(default_factory=list)
    subcommands: list[SubcommandSchema] = field(default_factory=list)
    subcommand_dest: str | None = None
    domain: str = "general"
    description: str = ""
    stdin: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    output: tuple[str, ...] = ()
    exit_codes: tuple[str, ...] = ()
    safeguards: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    input_schemas: tuple[PayloadSchema, ...] = ()
    output_schemas: tuple[PayloadSchema, ...] = ()
