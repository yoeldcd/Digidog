# Patching Tools

Use the harness-provided native patcher or Core text patch utility (`apply_text_patch`) to edit bounded files.

**Supported Formats and Modes**:

* `--format json` *(default)*: Structured JSON patch specification (`edits`, `creates`, `moves`, `deletes`).
* `--format native`: Native `*** Begin Patch` patch document.
* `--format auto`: Automatic format classification based on leading content.
* `--check`: Dry-run validation and preflight planning without writing to disk.

**Safeguards**:

* **Workspace Confinement**: Targets must be relative paths under the workspace root. Traversal (`../`) and reparse points (symlinks/junctions) are rejected.
* **Encoding & Line Endings**: UTF-8, UTF-8 with BOM, and UTF-16 encodings are preserved. CRLF and LF line endings in replacement anchors are matched tolerantly while preserving local file line endings.
* **Preflight & Atomic Transactions**: All operations are planned before execution; per-file atomic commit with automatic rollback on mid-batch failures.
* **Empty File Protection**: Reducing a file to 0 bytes or creating an empty file requires explicit `"allowEmptyResult": true`.

**1. JSON Format Specification**:

```powershell
$PATCH_SPEC = '{
  "creates": [{"path": "relative/path/new_file.ext", "content": "Complete UTF-8 content\n", "allowEmptyResult": false}],
  "edits": [{"path": "relative/path/file.ext", "allowEmptyResult": false, "replacements": [{"old": "exact old text", "new": "exact new text", "expectedOccurrences": 1}]}],
  "moves": [{"fromPath": "relative/old_path.ext", "toPath": "relative/new_path.ext"}],
  "deletes": [{"path": "relative/obsolete.ext"}]
}'
$PATCH_SPEC | py {LOCAL_BRAIN_SCRIPT} apply-patch --check --json
$PATCH_SPEC | py {LOCAL_BRAIN_SCRIPT} apply-patch --json
```

**Multiline JSON Specification (Recommended for long blocks)**:

```powershell
$patch = [ordered]@{
    edits = @([ordered]@{
        path = 'relative/path/file.ext'
        allowEmptyResult = $false
        replacements = @([ordered]@{
            old = $exactOldText
            new = $exactNewText
            expectedOccurrences = 1
        })
    })
}
$patch | ConvertTo-Json -Depth 8 -Compress | py {LOCAL_BRAIN_SCRIPT} apply-patch --check --json
$patch | ConvertTo-Json -Depth 8 -Compress | py {LOCAL_BRAIN_SCRIPT} apply-patch --json
```

**2. Native Format Specification**:

```powershell
$PATCH_NATIVE = '*** Begin Patch
*** Add File: relative/path/new_file.ext
+line 1
+line 2
*** Delete File: relative/path/obsolete.ext
*** Update File: relative/path/file.ext
*** Move to: relative/path/renamed.ext
@@
 context line before
-old line to remove
+new line to insert
 context line after
*** End Patch
'
$PATCH_NATIVE | py {LOCAL_BRAIN_SCRIPT} apply-patch --format native --check --json
$PATCH_NATIVE | py {LOCAL_BRAIN_SCRIPT} apply-patch --format native --json
```

Preserve CRLF or LF endings as they exist. If Brain reports an anchor, occurrence, path, or target error — stop and correct the patch.

**PROHIBITED**: Writing temporary files or scripts to invoke the patcher. Use only standard shell input. If that fails, report it.
