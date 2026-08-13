# Core Text Patch Utility (`apply_text_patch`)

## Overview

The `apply_text_patch` utility is a Core-owned, self-contained Python component responsible for parsing, validating, planning, and transactionally applying filesystem mutations below a trusted workspace root.

It supports two input specifications:

1. **JSON Specification**: Structured JSON document defining `edits`, `creates`, `moves`, and `deletes`.
2. **Native Patch Specification**: Human/agent-readable patch format delimited by `*** Begin Patch` and `*** End Patch` sentinels.

---

## Architecture & Ownership

- **Core Utility Location**: `core/utilities/apply_text_patch`
- **In-Process Facade**: `core/utilities/apply_text_patch/src/facade.py` (`apply_text_patch()`)
- **Standalone CLI Launcher**: `core/utilities/apply_text_patch/apply_text_patch.py`
- **Brain CLI Adapter**: `core/brain/src/brain/presentation/actions/utilities/command_apply_patch.py`

Brain's `apply-patch` command is a thin presentation adapter over this utility. Brain forwards stdin arguments, injects the active workspace root, and delegates execution directly to the Core facade.

---

## Formats and Parsing Modes

The utility accepts three format modes:

- `--format json` *(default)*: Parses standard JSON patch specifications.
- `--format native`: Parses native `*** Begin Patch` patch documents.
- `--format auto`: Automatically inspects leading text. If leading non-whitespace starts with `{`, it parses as JSON. If it starts with `*** Begin Patch`, it parses as Native. Otherwise, it raises a `PatchInputFormatError`.

---

## Shared Safety & Transactional Safeguards

Regardless of input format, all mutations pass through the same transactional engine (`FileSystemPatchEngine`):

1. **Workspace Confinement**: All target paths must be relative to the workspace root. Escape attempts (e.g. `../outside.txt` or absolute paths) are rejected.
2. **Reparse Point Rejection**: Targets or intermediate directory segments that resolve to symlinks or junctions are rejected.
3. **Encoding & Line Ending Preservation**:
   - Source files are strictly decoded (UTF-8, UTF-8 with BOM, UTF-16-LE, UTF-16-BE).
   - Existing BOM and encoding are preserved upon writing.
   - Line ending differences (CRLF vs LF) in replacement anchors are matched tolerantly while preserving local file line endings.
4. **Complete Preflight**: All operations in a batch are fully planned and verified in memory before any filesystem modification.
5. **Atomic Commit & Rollback**:
   - Each file write is written to a temporary file in the same parent directory, verified, and atomically replaced (`os.replace`).
   - If a failure occurs mid-batch, committed changes are rolled back in reverse order, restoring original file contents and removing created files.
6. **Source Redaction**: Hashes, byte counts, and execution metrics are logged internally; error payloads and check outputs redact actual file contents.

---

## Transient Rollback Storage

`transient_dir` in `core/configs/brain_configs.json` is a base directory. The patcher writes owned rollback artifacts only under its `patches_rollback` child; for example, `E:\.tmp` resolves to `E:\.tmp\patches_rollback`. If the configured base is absent or invalid, a consumer resolves `<workspace>/$agent/.tmp/patches_rollback`. The engine receives this resolved directory explicitly and never invents another fallback.

## Input Contracts & Examples

### 1. JSON Contract Specification

Top-level JSON schema supporting four array attributes: `edits`, `creates`, `moves`, and `deletes`.

```json
{
  "creates": [
    {
      "path": "src/application/config.py",
      "content": "ENABLE_FEATURE = True\n",
      "allowEmptyResult": false
    }
  ],
  "edits": [
    {
      "path": "src/application/service.py",
      "allowEmptyResult": false,
      "replacements": [
        {
          "old": "def process():\n    pass",
          "new": "def process():\n    return True",
          "expectedOccurrences": 1
        }
      ]
    }
  ],
  "moves": [
    {
      "fromPath": "src/legacy/old_service.py",
      "toPath": "src/application/old_service.py"
    }
  ],
  "deletes": [
    {
      "path": "src/obsolete.py"
    }
  ]
}
```

#### Key JSON Rules

- `path`, `fromPath`, `toPath`: Must be non-empty workspace-relative strings.
- `replacements`: Non-empty array of objects containing non-empty `old`, string `new`, and positive integer `expectedOccurrences` (defaults to 1).
- `allowEmptyResult`: Optional boolean (default `false`). Creating an empty file or editing a file to 0 bytes requires `allowEmptyResult: true`.

---

### 2. Native Contract Specification

Text document enclosed between `*** Begin Patch` and `*** End Patch`. Supports `Add File`, `Delete File`, `Update File`, and optional `*** Move to:` relocation.

```diff
*** Begin Patch
*** Add File: src/new_module.py
+class NewModule:
+    pass
*** Delete File: src/old_module.py
*** Update File: src/existing.py
*** Move to: src/renamed.py
@@
 context before
-line to remove
++line to add
 context after
*** End Patch
```

#### Key Native Rules

- **Add File**: Lines in body must begin with `+`.
- **Delete File**: Must have no body.
- **Update File**: Contains one or more hunks starting with `@@` or `@@ <section context>`. Lines use ` ` for context, `-` for removal, and `+` for addition.
- **Context matching**: Resolves each hunk in declaration order using exact lines first, then right-trimmed and fully stripped line comparison.
- **End of file**: `*** End of File` constrains a hunk to the final matching block and permits an otherwise anchorless append.
- **Patch newlines**: The patch document's terminal newline never changes the target hunk anchor or target file newline policy.
- **Move to**: Optional directive immediately following `*** Update File: <path>`.

---

## Command-Line Usage (CLI)

### Core Standalone Launcher

```powershell
# Apply JSON patch from stdin
$PATCH_JSON | py core/utilities/apply_text_patch/apply_text_patch.py --json

# Dry-run native patch validation without writing to disk
$PATCH_NATIVE | py core/utilities/apply_text_patch/apply_text_patch.py --format native --check --json
```

### Brain Facade Launcher

```powershell
# Dry-run check via Brain CLI
$PATCH_JSON | py '$agent/scripts/brain.py' apply-patch --check --json

# Apply native patch via Brain CLI
$PATCH_NATIVE | py '$agent/scripts/brain.py' apply-patch --format native --json
```

---

## Programmatic Usage (Python Facade)

```python
from pathlib import Path
from utilities.apply_text_patch.src.facade import (
    apply_text_patch,
    PatchInputFormat,
    PatchResult,
    PatchSpecificationError,
    PatchExecutionError,
)

workspace_root = Path("/path/to/workspace")
transient_dir = Path("/path/to/transient/patches_rollback")
patch_content = '{"creates": [{"path": "hello.txt", "content": "world\\n"}]}'

try:
    result: PatchResult = apply_text_patch(
        serialized_specification=patch_content,
        workspace_root=workspace_root,
        transient_dir=transient_dir,
        check=False,
        input_format=PatchInputFormat.JSON,
    )
    print(f"Applied patch to {len(result.files)} file(s).")
except PatchSpecificationError as exc:
    print(f"Invalid patch specification: {exc}")
except PatchExecutionError as exc:
    print(f"Execution failed: {exc}")
```
