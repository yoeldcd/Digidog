# Apply Text Patch CLI Command

## Overview

The `apply-patch` Brain utility applies deterministic exact-text replacements and new file creations through a guarded Python vertical (`brain.application.patching` and `brain.infrastructure.patching`). It accepts a JSON specification on standard input, validates target paths, anchors, occurrences, strict encodings, and physical path confinement in memory, and performs per-file atomic replacements with batch rollback upon failure.

## `apply-patch`

**What It Does:** Executes a validated JSON patch through the typed Python engine and returns a compact semantic result. Hashes and byte lengths remain internal integrity evidence.

**Use It When:** Any repository text file must be modified or created through standard input specifications.

**Result:** In normal mode, validated targets are updated atomically per file. In `--check` mode, the exact validation and planning execute without disk writes.

| Parameter | Required | Default | Description |
|---|---|---|---|
| standard input | Yes | None | JSON object containing `edits` and/or `creates` arrays. |
| `--check` | No | Disabled | Validate and report evidence without writing. |
| `--json` | No | Disabled | Return compact mode and affected-file facts as JSON. |

### Specification Contract

```json
{
  "creates": [
    {
      "path": "src/new_file.py",
      "content": "VALUE = 123\n"
    }
  ],
  "edits": [
    {
      "path": "src/example.ts",
      "replacements": [
        {
          "old": "before",
          "new": "after",
          "expectedOccurrences": 1
        }
      ]
    }
  ]
}
```

Every `path` must be workspace-relative. `old` anchors must be non-empty strings. `expectedOccurrences` defaults to `1` and must match target occurrences exactly. CRLF, LF, and CR boundaries are equivalent for multiline anchors, while replacements preserve the matched file style. Reducing a file to 0 bytes or creating an empty file requires `allowEmptyResult: true`.

### Compact JSON Result

```json
{
  "ok": true,
  "command": "apply-patch",
  "mode": "check",
  "files": [
    {"path": "src/example.ts", "operation": "edit", "replacements": 1}
  ]
}
```

Successful payloads omit hashes, lengths, rollback, cleanup, recovery artifacts, and rendered output. Failure payloads add only facts that exist and are actionable.

### Usage

```powershell
$PATCH_SPEC = '{"edits":[{"path":"src/example.ts","replacements":[{"old":"before","new":"after","expectedOccurrences":1}]}]}'
$PATCH_SPEC | py '$agent/scripts/brain.py' apply-patch --check --json
$PATCH_SPEC | py '$agent/scripts/brain.py' apply-patch --json
```