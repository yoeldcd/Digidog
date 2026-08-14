# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the user-only generate-pwd CLI command."""

from __future__ import annotations

from brain.presentation.commands.models import (
    ArgumentSchema,
    CommandSchema,
    PayloadSchema,
    SchemaField,
)


OUTPUT_SCHEMA = PayloadSchema(
    name="generate_pwd_result",
    media_type="application/json",
    description="Successful hash-only result. The source input is never part of the payload.",
    fields=(
        SchemaField("ok", "boolean", True, "Always true for a successful invocation."),
        SchemaField("command", "string", True, "Canonical command name."),
        SchemaField(
            "hash",
            "lowercase SHA-256 hexadecimal string",
            True,
            "64-character digest of the UTF-8 input.",
        ),
    ),
    example=(
        '{"ok":true,"command":"generate-pwd","hash":"<64 lowercase hexadecimal characters>"}',
    ),
)


SCHEMA = CommandSchema(
    name="generate-pwd",
    domain="general",
    help="Generate a UTF-8 SHA-256 digest from hidden or strictly framed standard-input text.",
    arguments=[
        ArgumentSchema(
            flags=["--stdin"],
            action="store_true",
            help="Read exactly one non-empty input line from standard input.",
        ),
    ],
    description=(
        "Generate one lowercase SHA-256 digest for user-owned input. "
        "The command accepts no password value, text positional, or value flag."
    ),
    stdin=(
        "Without --stdin, read one non-empty value through the hidden password reader.",
        "With --stdin, read exactly one non-empty line and reject multiline input.",
    ),
    examples=(
        "py {LOCAL_BRAIN_SCRIPT} generate-pwd --authority user",
        "py {LOCAL_BRAIN_SCRIPT} generate-pwd --stdin --authority user",
        "py {LOCAL_BRAIN_SCRIPT} generate-pwd --stdin --json --authority user",
    ),
    output=(
        "Terminal mode prints only the lowercase 64-character SHA-256 digest.",
        "JSON mode emits exactly the ok, command, and hash fields on success.",
    ),
    exit_codes=(
        "0 when a digest is generated.",
        "1 when authority, input framing, or input availability is invalid.",
    ),
    safeguards=(
        "Requires the exact --authority user value and denies every other authority before reading input.",
        "Never prints, logs, persists, or narrates the source input.",
        "JSON invocations must use --stdin instead of prompting.",
    ),
    notes=(
        "The digest is computed from the original UTF-8 text without trimming.",
        "The --stdin input utility removes one terminal line ending and rejects empty or multiline input.",
    ),
    output_schemas=(OUTPUT_SCHEMA,),
)
