# Author: Yoel David <yoeldcd@gmail.com>
# X: https://x.com/SAY6267

"""Command metadata for the guarded repository patch applicator."""

from __future__ import annotations

from brain.presentation.commands.models import (
    ArgumentSchema,
    CommandSchema,
    PayloadSchema,
    SchemaField,
)

REPLACEMENT_SPEC = PayloadSchema(
    name="replacement_spec",
    media_type="application/json",
    description="Replacement specification. Unknown fields are rejected.",
    fields=(
        SchemaField("old", "nonempty string", True, "Exact text to replace."),
        SchemaField("new", "string", True, "Replacement text; empty is allowed."),
        SchemaField(
            "expectedOccurrences",
            "positive integer",
            False,
            "Expected match count; defaults to 1.",
        ),
    ),
    example=('{"old":"old line","new":"new line","expectedOccurrences":1}',),
)

EDIT_OPERATION = PayloadSchema(
    name="edit_operation",
    media_type="application/json",
    description="Existing-file edit. Unknown fields are rejected.",
    fields=(
        SchemaField("path", "string", True, "Workspace-relative file path."),
        SchemaField(
            "replacements",
            "nonempty array<replacement_spec>",
            True,
            "Ordered replacements.",
        ),
        SchemaField(
            "allowEmptyResult", "boolean", False, "Allow an empty resulting file."
        ),
    ),
    example=('{"path":"src/file.py","replacements":[{"old":"old","new":"new"}]}',),
)

CREATE_OPERATION = PayloadSchema(
    name="create_operation",
    media_type="application/json",
    description="New-file creation. Unknown fields are rejected.",
    fields=(
        SchemaField("path", "string", True, "Workspace-relative destination path."),
        SchemaField("content", "string", True, "UTF-8 file content."),
        SchemaField("allowEmptyResult", "boolean", False, "Allow empty content."),
    ),
    example=('{"path":"src/new.py","content":"print(1)\\n"}',),
)

MOVE_OPERATION = PayloadSchema(
    name="move_operation",
    media_type="application/json",
    description="File move. Unknown fields are rejected.",
    fields=(
        SchemaField("fromPath", "string", True, "Workspace-relative source path."),
        SchemaField("toPath", "string", True, "Workspace-relative destination path."),
    ),
    example=('{"fromPath":"src/old.py","toPath":"src/new.py"}',),
)

DELETE_OPERATION = PayloadSchema(
    name="delete_operation",
    media_type="application/json",
    description="File deletion. Unknown fields are rejected.",
    fields=(SchemaField("path", "string", True, "Workspace-relative path to remove."),),
    example=('{"path":"src/obsolete.py"}',),
)

JSON_PATCH_REQUEST = PayloadSchema(
    name="json_patch_request",
    media_type="application/json",
    description="Strict patch object; unknown fields are rejected and at least one operation is required.",
    fields=(
        SchemaField(
            "edits", "array<edit_operation>", False, "Existing-file replacements."
        ),
        SchemaField("creates", "array<create_operation>", False, "New files."),
        SchemaField(
            "moves", "array<move_operation>", False, "Source/destination moves."
        ),
        SchemaField(
            "deletes", "array<delete_operation>", False, "Existing paths to remove."
        ),
    ),
    example=(
        (
            '{\n  "edits": [{"path": "src/file.py", "replacements": '
            '[{"old": "old", "new": "new"}]}],\n'
            '  "creates": [], "moves": [], "deletes": []\n}'
        ),
    ),
)

NATIVE_PATCH_TEXT = PayloadSchema(
    name="native_patch_text",
    media_type="text/plain",
    description="Native patch text using Begin/End Patch; supports Add, Update, Delete, and Move directives, named context anchors, whitespace matching, start insertion, and EOF insertion. Check mode performs validation without writes.",
    fields=(SchemaField("text", "string", True, "Multiline native patch text."),),
    example=(
        "*** Begin Patch\n*** Add File: src/new.py\n+hello\n*** Update File: src/file.py\n@@\n-old\n+new\n*** Move to: src/moved.py\n*** Delete File: src/obsolete.py\n*** End Patch",
    ),
)

FILE_RESULT = PayloadSchema(
    name="file_result",
    media_type="application/json",
    description="Redacted affected-file evidence.",
    fields=(
        SchemaField("path", "string", True),
        SchemaField("operation", "string", True),
        SchemaField(
            "replacements",
            "positive integer",
            False,
            "Included for edit operations when nonzero.",
        ),
    ),
    example=('{"path":"src/file.py","operation":"edit","replacements":1}',),
)

PATCH_SUCCESS = PayloadSchema(
    name="patch_success",
    media_type="application/json",
    description="Successful check or apply result.",
    fields=(
        SchemaField("ok", "boolean", True),
        SchemaField("command", "string", True),
        SchemaField("mode", "string", True, "check or apply."),
        SchemaField("files", "array<file_result>", True),
    ),
    example=(
        (
            '{"ok":true,"command":"apply-patch","mode":"check",'
            '"files":[{"path":"src/file.py","operation":"edit","replacements":1}]}'
        ),
    ),
)

PATCH_ERROR = PayloadSchema(
    name="patch_error",
    media_type="application/json",
    description="Source-redacted failure result; mode is not required.",
    fields=(
        SchemaField("ok", "boolean", True),
        SchemaField("command", "string", True),
        SchemaField("error", "string", True),
        SchemaField("files", "array<file_result>"),
        SchemaField("rollback", "string"),
        SchemaField("cleanup", "string"),
        SchemaField("recoveryArtifacts", "array<string>"),
    ),
    example=(
        (
            '{"ok":false,"command":"apply-patch","error":"patch failed",'
            '"rollback":"completed","recoveryArtifacts":["path"]}'
        ),
    ),
)

# Backward-compatible local aliases used by callers.
JSON_PATCH_INPUT = JSON_PATCH_REQUEST
NATIVE_PATCH_INPUT = NATIVE_PATCH_TEXT
PATCH_OUTPUT = PATCH_SUCCESS

SCHEMA = CommandSchema(
    name="apply-patch",
    domain="utilities",
    help="Validate and apply an exact JSON or contextual native patch from standard input.",
    arguments=[
        ArgumentSchema(
            flags=["--check"],
            action="store_true",
            help="Validate and report the complete patch without writing files.",
        ),
        ArgumentSchema(
            flags=["--format"],
            default="json",
            help="Input format: json, native, or auto. Defaults to json.",
        ),
    ],
    description="Validate and apply a JSON or contextual native patch read from standard input.",
    stdin=(
        "JSON mode accepts one patch object; native mode accepts contextual unified patch text.",
    ),
    examples=(
        "py {LOCAL_BRAIN_SCRIPT} apply-patch --format json < patch.json",
        "py {LOCAL_BRAIN_SCRIPT} apply-patch --check --format native < patch.diff",
    ),
    output=("Validation or applied-file summary in JSON/text form.",),
    exit_codes=(
        "0: patch validated or applied.",
        "1: malformed patch, confinement violation, or write failure.",
    ),
    safeguards=(
        "--check performs no writes; applied paths are transactionally validated and confined to the workspace.",
    ),
    notes=(
        "Formats are json, native, and auto; auto detects JSON before contextual native text.",
    ),
    input_schemas=(
        JSON_PATCH_REQUEST,
        REPLACEMENT_SPEC,
        EDIT_OPERATION,
        CREATE_OPERATION,
        MOVE_OPERATION,
        DELETE_OPERATION,
        NATIVE_PATCH_TEXT,
    ),
    output_schemas=(PATCH_SUCCESS, PATCH_ERROR, FILE_RESULT),
)
