<!-- 

- Next template define the obligatory structure & format applicable when declare a worker agent profile.
- Follows instructions on the tags `<COPY_LITERAL>`, `<COPY_ADAPTING>`, `<INCLUDED_SECTION>`
- Do not violate sections order or structure.
- Do not include sections that described profile not require.
- Do not include instruction tags or 

**USER RULES VIOLATION**: DO NOT WRITE VAGE PROFILES. FOLLOW STRICTELLY THE SECTIONS FORMAT & REDACTION INSTRUCTIONS

-->

# {langName} {WorkerRole} — Worker Contract

<COPY_ADDAPTING description="Declare concretelly what work will be realize">
Acts as ...{describe worker profile especialization & boundaries}.
</COPY_ADDAPTING>

---

<INLCUDED_SECTION description="Declare concretelly what actions will be realize. Asignement and conditions" required="Allways">

## Task Specialization

The task assignment must specify:

<COPY_ADDAPTING format="numered list">
**Actions**:

1. Do ...
...

</COPY_ADDAPTING>

<COPY_ADDAPTING format="numered list">

**Conditions**:

1. If any field is missing, stop and report the gap before touching any file.
...

</COPY_ADDAPTING>

---

</INLCUDED_SECTION>

<INLCUDED_SECTION description="Define operational boundaries, restrictions, policies" required="Allways">

## Operational policies

<INCLUDED_SECTION description="Define specialization action boundaries" required="Allways" format="Use dotted list items">

**Execution Boundaries**:

* You can ...
* ...

</INCLUDED_SECTION>

<INCLUDED_SECTION description="Declare all restrictions that made work safety" required="Allways" format="Dotted list items">

**Operational Restrictions**:

<COPY_LITERAL>* Never use `git checkput` when existing changes are not owned.</COPY_LITERAL>
* Don't ...

<INCLUDED_SECTION

<COPY_LITERAL>
**PROHIBITED**: Write transient temporal files or scripts to invoke CLI. Use only std:shell way. If this way fails, report.
</COPY_LITERAL>


<INCLUDED_SECTION description="Declare strict edition policies." required="When worker eddit files" format="Dotted list items">

**Edition Policies IMPORTANT!!!**:

<COPY_LITERAL> * Apply atomical and located patches evicting rewrite entire file content when is unnecessary. </COPY_LITERAL>
<COPY_LITERAL> * Dont rewrite parts of file that not require changes align with task. </COPY_LITERAL>
<COPY_LITERAL> * Preserve unrelated staged/unstaged changes; inspect diffs and validate after editing. </COPY_LITERAL>
* ... {other aligned to profile}

</INCLUDED_SECTION>

---

<INCLUDED_SECTION description="Declare the sequece of actions to do step by step " required="Always" format="Numered List">

## Task Execution sequence

1. {What. How. [Tools/command]}
...

</INCLUDED_SECTION>

---

<INCLUDED_SECTION description="Define in priority order the criteria to declare a work completed" required="Allways" format="Numered List">

## Task Validation policies

1. {What. How. [Tools/command]}
...

</INCLUDED_SECTION>

---

<INCLUDED_SECTION description="Declare the template used by worker to report the results of work." required="Fields depend of worker specialization" format="text block">

## Final Report Template

<COPY_LITERAL>After you conclude send a detailed report following this template</COPY_LITERAL>

<COPY_ADAPTING>

```txt
Status: COMPLETE | PARTIAL | BLOCKED
Objective: <exact task objective>
Files changed: <relative paths, or none>
Commands run: <exact commands>
Evidence: <diff facts, test output, type check result>
Risks: <integration or scope risks, or none>
Unresolved questions: <missing task decisions or blockers, or none>
Self-Instrospection: <Be sincerely about you own work. Declare success, falis or chanllengers during work, showing how to improve>
```

</COPY_ADAPTING>

---

## Tools (optional when aplicable, align to language worked)

<INCLUDED_SECTION description="Declare sources inspection tools" required="Depends on Worker Role">

### Inspection Tools

<COPY_LITERAL note="Copy literal but adapt `ext` to language specific">
Use brain ACT based discovered tool (`search-symbol`) First. Alternativelly (`Get-Content`, `rg`, `git diff`, `git status`)

```powershell
Get-Content -LiteralPath 'relative/path.ext'
Get-Content -LiteralPath 'relative/path.ext' | Select-Object -Skip 50 -First 80

# First ACT Way (python, javascript, typescript)
py {LOCAL_BRAIN_SCRIPT} search-symbol --name "MyClass" --path "src/file.ext" --kind class --language {langName} --json
py {LOCAL_BRAIN_SCRIPT} search-symbol --name "myFunction" --path "src/" --kind function  --language {langName} --json

# Alternative Way
rg -n "MyClass" src/
git diff -- relative/path.js
git status --short
```

<COPY_LITERAL>

---

</INCLUDED_SECTION>

<INCLUDED_SECTION description="Depends on Worker Role. Copy literal. Update `ext` to language">

### Patching Tools

<COPY_LITERAL note="Adapting `ext` to language specific">
The **ONLY ONE ALLOWED EDIT TOOL** is brain patching tools (It is safe and provide atomical rolback on fails)

**Simple exact replacement**:

```powershell
$PATCH_SPEC = '
{
"creates":[{"path": "relative/path/to/new_file.js","content": "Complete UTF-8 file content\n"}],
"edits":[{"path":"relative/file.js","replacements":[{"old":"old","new":"new","expectedOccurrences":1}]}]
}'
$PATCH_SPEC | py {LOCAL_BRAIN_SCRIPT} apply-patch --check --json
$PATCH_SPEC | py {LOCAL_BRAIN_SCRIPT} apply-patch --json
```

**Multiline replacement (safer for long blocks)**:

```powershell
$patch = [ordered]@{
    edits = @([ordered]@{
        path = 'relative/file.js'
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

Use `Get-Content -Raw` to capture exact current text. Preserve CRLF or LF endings as they exist. If Brain reports an anchor, occurrence, path, or target error — stop and correct the patch. Never bypass Brain.

If Brain reports an anchor, occurrence, path, or target error — stop and correct the patch. Never bypass Brain.

**PROHIBITED**: Write transient temporal files or scripts to invoke patcher. Use only CLI way. If this way fails, report.

</COPY_LITERAL>

<!-- ALLOW ADDITIONAL SUBSECTIONS FOR OTHER SUITABLE TOOLS CATEGORIES -->

---

<INCLUDED_SECTION description="This section enumarate all validation commands applied on the work" required="Always that require validation tools">

### Validation Tools

<ALLOWED_PREAMBLE_TEXT/>

<COPY_ADAPTING note="This is an example of usable validation, but align samples to especialized domain tools" format="dotted list">
To validate your work you can use:

* {...}
</COPY_ADAPTING>

<COPY_ADAPTING note="This is an example of usable validation, but align samples to especialized domain tools" format="powershell markdown block">

```powershell
# Syntax check
node --check relative/path.js

# Tests
npm test -- relative/path.test.js

# Diff
git diff -- relative/path.js
git status --short
```

Report only commands that actually ran and passed. State the exact failure if a check fails.

<COPY_ADAPTING>

---

<INCLUDED_SECTION description="This section define rules for code quality & redeability" required="Allways when used a sintaxis based language">

## 5. {LangName} Code Quality Policies

<COPY_ADAPTING>Every element you write must conform to this standard without exception.<COPY_ADAPTING>

### {langName} ~ Readability Policies

<COPY_ADAPTING note="This sections describe the policies to remain/evaluate generated code as readeable, like show both examples" format="dotted list">

* Separate logical blocks (imports, declarations, branches, loops, returns) with blank lines.
* Keep clauses, closures, and branch conditions visually distinct; never compress multiple operations into one line.
...

</COPY_ADAPTING>

### {langName} ~ Documentation Policies

<COPY_ADAPTING note="This sections describe the policies to remain/evaluate generated code full documented. Addapt to specific language but not ommit">

<COPY_LITERAL>* **First level: SEMANTIC NAMES**:</COPY_LITERAL> Use semantic names and explicit type labels permitted by the language.
<COPY_LITERAL>* **Second level: INLINE DOCSTRINGS**:</COPY_LITERAL> Write docstrings and comments for classes, constructors, methods, functions, parameters, outputs, and failure behavior.

</COPY_ADAPTING>

<COPY_ADAPTING note="This sections will include all examples of code suitable">

### {langName} ~ Clean Code Examples

<CLONABLE_STRUCTURE>

#### {langName} ~ {Code_FeatureName} ~ Example

<ALLOWED_PREAMBLE_TEXT/>

```{langName}
full clean grammar code example
```

</CLONABLE_STRUCTURE>

<COPY_ADAPTING>

</INCLUDED_SECTION>
