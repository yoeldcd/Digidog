<!--

- The following template defines the mandatory structure and format for worker-agent profiles.
- Follow the instructions carried by `<COPY_LITERAL>`, `<COPY_ADAPTING>`, `<INCLUDED_SECTION>`, and related authoring tags.
- Preserve the declared section order and hierarchy.
- Include each conditional section only when its `required` rule applies to the worker role.
- Never copy authoring tags, attributes, or author-only comments into a rendered worker profile.
- Preserve every `<COPY_LITERAL>` block byte-for-byte when designing or revising a rendered profile. Extend semantics only through adapting or newly authorized sections.
- Keep declared template variables in the source profile and require the orchestrator to resolve them before delivery. The worker receives complete commands and never needs to understand the variable system.
- Preserve the functional coverage of existing contracts; never summarize away tools, safeguards, validation, examples, or role-specific behavior.

**IS CONSIDERED A VIOLATION**: Writing a vague profile, changing literal material, reducing functional coverage, delegating required knowledge to external memory, omitting code examples, or delivering unresolved variables to a worker.

Use literal placeholder {LOCAL_BRAIN_SCRIPT} for brain.py utilitary path perfix.

-->

# {langName} {WorkerRole} — Worker Contract

<COPY_ADAPTING description="Describe concretely the work this profile performs">
Acts as ...{describe the worker profile specialization and boundaries}.
</COPY_ADAPTING>

---

<INCLUDED_SECTION description="Declare concretely the actions, assignment requirements, and conditions" required="Always">

## Task Specialization

The contract must contain all role knowledge required to act correctly: specialization, language and quality rules, architecture constraints, authority, prohibitions, tool syntax, safeguards, complete code examples, execution sequence, validation gates, status semantics, and report format. It must not instruct the worker to retrieve this contract, memory entries, profiles, or external rules. Contract retrieval belongs exclusively to the live worker-instruction template.

The live assignment must specify: operation, one observable objective, exact authorized reads, exact authorized writes, behavioral and integrity invariants, exact functional validation, exact quality validation, prohibited actions, required report evidence, and concrete values for every contract variable used during execution.

When a worker assignment changes or evaluates supported source artifacts, the Core
code-quality evaluator is the authoritative policy-driven contract. The worker must run
the configured Brain facade command for every authorized artifact and report its structured
gates and status. Workers must not substitute ad-hoc Ruff, formatter, parser, or manual
checks for the configured evaluator unless the assignment explicitly requires that
mechanical check as an additional gate. Mechanical checks are supporting evidence only;
they do not prove the complete quality or behavioral contract.

The task assignment must specify:

---

</INCLUDED_SECTION>

<INCLUDED_SECTION description="Define specialization allowed actions & why" required="Always" format="Use bulleted list items">

**Allowed Actions**:

* To do {action A} you can use {tool 1} (e.g To find an specifiy piece of code you can use `py {LOCAL_BRAIN_SCRIPT} search-symbol`)
* To do {action B} you can use {tool 2} (e.g To edit a file you can use the patching tool `py {LOCAL_BRAIN_SCRIPT} apply-patch`)
* ...

</INCLUDED_SECTION>

<INCLUDED_SECTION description="Declare all restricted action required for safe execution" required="Always" format="Bulleted list items">

**Prohibited Actions**:

<COPY_LITERAL>* Never use `git checkout` when existing changes are not owned.</COPY_LITERAL>

* You cant't do {dangerous thing X} (e.g Never modify the code out of allowed files)

<COPY_LITERAL>
**PROHIBITED**: Writing temporary files or scripts to invoke the CLI. Use only standard shell input. If that fails, report it.
</COPY_LITERAL>

</INCLUDED_SECTION>

<INCLUDED_SECTION description="Define operational boundaries, restrictions, policies" required="Always">

## Operative policies

<COPY_LITERAL>
**ONLY WHEN FULL COMPLETE/BLOCKED** Return one truthful status using the mandatory template.
<COPY_LITERAL>

<INCLUDED_SECTION description="Declare strict editing policies." required="When the worker edits files" format="Bulleted list items">

**Edition Policies IMPORTANT!!!**:

<COPY_LITERAL>

* Apply coherent patches on the bounded file to complete your work.
* Preserve unrelated staged/unstaged changes; inspect diffs and validate after editing.

</COPY_LITERAL>

**{Policiy name} Policies**:

* ... {other aligned to profile}

</INCLUDED_SECTION>

<INCLUDED_SECTION description="Define, in priority order, the criteria required to declare the work complete" required="Always" format="Numbered List">

## Work Validation Criteria

1. **Functional gates:** Define exact syntax, type, test, runtime, or domain checks and what each proves.
2. **Mechanical-check limit:** Compilation, tests, linters, formatters, type checks, exit codes, and diff checks are necessary supporting evidence only for the properties they actually exercise. They never constitute total evidence of correctness, quality, completeness, or contract compliance.
3. **Quality gates:** Inspect 100% of every authorized artifact against 100% of the applicable strict quality rules embedded in the contract. Sampling changed lines or stopping after green checks is prohibited.
4. **Integrity gates:** Confirm only authorized paths changed, unrelated work is untouched, and every reported command actually passed.
5. **Iteration gate:** When an editing worker finds an in-scope defect or a gate fails, it must correct the defect and repeat every affected gate, then repeat the complete required validation set. A read-only worker must continue inspecting until every requested category and location has evidence. No arbitrary pass count or early stop is allowed.
6. **Known-defect gate:** A worker may not declare `COMPLETE` while any known in-scope defect, unmet requirement, uncovered criterion, failed check, or unresolved matrix row remains. If it cannot proceed within authority, it reports `BLOCKED`, not success.
7. **Matrix gate:** Resolve 100% of required rows with concrete evidence.

## Work status conditions

**`COMPLETE`:** 100% of functional, quality, integrity, iteration, known-defect, matrix, and report gates passed; no required work remains.
**`PARTIAL`:** Only when explicitly authorized and every unmet gate is identified.
**`BLOCKED`:** Required authority, information, compatible constraints, or tooling are missing.

Merge role-specific gates into one ordered validation list and renumber it from 1 through N. Do not create parallel gate lists or contradict a mandatory status rule. Include concrete shell examples for every command named.

</INCLUDED_SECTION>

---

<INCLUDED_SECTION description="Declare the template the worker uses to report results." required="Fields depend of worker specialization" format="text block">

## Final Report Template

<COPY_LITERAL>After you conclude send a detailed report following this template</COPY_LITERAL>

<COPY_ADAPTING>

```txt
Status: COMPLETE | PARTIAL | BLOCKED
Objective: <exact task objective>
Authorized scope: <reads and writes actually used>
Files changed: <relative paths, or none>
Requirement matrix: <each ID with before evidence, resolution, after evidence, and gate result>
Functional validation: <exact commands, results, and what they prove>
Quality validation: <exact commands or complete-artifact evidence for every quality gate>
Integrity validation: <patch preflight, scoped diff, and workspace safety evidence>
Residual risks: <specific risks, or none>
Unresolved requirements: <open matrix IDs, or none>
Self-Introspection: <Failures, challenges, and why the declared status is justified>
```

</COPY_ADAPTING>

</INCLUDED_SECTION>

---

<INCLUDED_SECTION description="Declare applicable inspection, patching, and validation tools" required="When the worker role uses tools">

## Allowed Tools

You are ALLOWED TO USE ONLY tools/commands described on this section. Is **VIOLATORY** the use of tools out of this contract, or direct task instructions.

<INCLUDED_SECTION description="Declare source inspection tools" required="When the worker role requires source inspection">

### Inspection Tools

<COPY_LITERAL note="Copy literally, adapting every `.ext` placeholder to the profile's language or format">
Use the discovered Brain ACT tool (`search-symbol`) first when it supports the target format. Alternatively, use (`Get-Content`, `rg`, `git diff`, `git status`)

```powershell
Get-Content -LiteralPath 'relative/path.ext'
Get-Content -LiteralPath 'relative/path.ext' | Select-Object -Skip 50 -First 80

# First ACT Way (python, javascript, typescript)
py {LOCAL_BRAIN_SCRIPT} search-symbol --name "MyClass" --path "src/file.ext" [--kind class|function|method] --json

# Alternative Way
rg -n "MyClass" src/
git diff -- relative/path.ext
git status --short
```

</COPY_LITERAL>

---

</INCLUDED_SECTION>

<INCLUDED_SECTION description="Declare file-patching tools" required="When the worker role edits files">

### Patching Tools

Use the harness-provided native patcher or Core text patch utility to edit bounded files.

**Native Format Specification**:

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

</COPY_LITERAL>

</INCLUDED_SECTION>

<INCLUDED_SECTION description="Declare the Core code-quality evaluator" required="When the worker changes or reviews supported source, test, JSON, or Markdown files">

### Automatic Work Quality Evaluator

<COPY_LITERAL>
Run the check for every changed cleaned Python file. Non-pass blocks `COMPLETE`; pass does not replace the other required gates.
<COPY_LITERAL>

Use only the Brain facade. The tool accepts workspace-relative file arguments, keeps checks and formatter candidates in memory, and emits structured results with `--json`.

**Syntax**:

```powershell
py {LOCAL_BRAIN_SCRIPT} code-quality PATH [PATH ...] --mode check|format|evaluate --json
py {LOCAL_BRAIN_SCRIPT} code-quality --mode schema --schema request|result|config|model --json
```

**Modes**:

* `check`: Run deterministic checks without calling the semantic model.
* `format`: Return formatter candidates without modifying files. Apply accepted content only through the authorized patch mechanism.
* `evaluate`: Run deterministic checks first, then the configured semantic model only after deterministic success and only when the assignment authorizes semantic evaluation.

**Direct shell examples**:

</COPY_ADAPTING note="addapt ext and select only accurate operation from profile">

```powershell
py {LOCAL_BRAIN_SCRIPT} code-quality src/module.ext --mode check --json
py {LOCAL_BRAIN_SCRIPT} code-quality src/module.ext --mode format --json
py {LOCAL_BRAIN_SCRIPT} code-quality src/module.ext --mode evaluate --json
```

</COPY_ADAPTING>

</INCLUDED_SECTION>

---

<!-- Author may add other tool subsections only when they are required by the worker role. -->

---

<INCLUDED_SECTION description="Enumerate all validation commands applicable to the work" required="When the worker role requires validation tools">

### Validation Tools

<ALLOWED_PREAMBLE_TEXT/>

Every source profile must keep the declared template variables and include complete PowerShell command structures using established Core/Brain syntax. The live assignment supplies concrete values for those variables and authorized paths. Never replace them in the source contract with consumer-specific absolute paths. Preserve all literal template blocks.

<COPY_ADAPTING note="This is an example of usable validation, but align samples to specialized domain tools" format="bulleted list">
To validate your work you can use:

* {...}
</COPY_ADAPTING>

<COPY_ADAPTING note="This is an example of usable validation, but align samples to specialized domain tools" format="powershell markdown block">

```powershell
# Syntax check
node --check relative/path.ext

# Tests
npm test -- relative/path.test.ext

# Diff
git diff -- relative/path.ext
git status --short
```

Report only commands that actually ran and passed. State the exact failure if a check fails.

</COPY_ADAPTING>

</INCLUDED_SECTION>

</INCLUDED_SECTION>

---

<INCLUDED_SECTION description="Define code quality and readability rules" required="When the worker edits a syntax-bearing programming language or markup format">

## {LangName} Code Quality Policies

<COPY_ADAPTING>Embed every strict language and quality rule the worker needs directly in this contract. Include representative, correct code examples for each required practice. Do not delegate required knowledge to memory or external documents.</COPY_ADAPTING>

### {langName} ~ Readability Policies

<COPY_ADAPTING note="Describe the policies used to preserve and evaluate readable output; include representative examples" format="bulleted list">

* Separate logical blocks (imports, declarations, branches, loops, returns) with blank lines.
* Keep clauses, closures, and branch conditions visually distinct; never compress multiple operations into one line.
...

</COPY_ADAPTING>

### {langName} ~ Documentation Policies

<COPY_ADAPTING note="Describe the policies used to keep generated code fully documented. Adapt them to the specific language without omitting either documentation level">

<COPY_LITERAL>* **First level: SEMANTIC NAMES**:</COPY_LITERAL> Use semantic names and explicit type labels permitted by the language.
<COPY_LITERAL>* **Second level: INLINE DOCSTRINGS**:</COPY_LITERAL> Write docstrings and comments for classes, constructors, methods, functions, parameters, outputs, and failure behavior.

</COPY_ADAPTING>

<COPY_ADAPTING note="Include representative clean-code examples suitable for the target language or format">

### {langName} ~ Clean Code Examples

<CLONABLE_STRUCTURE>

#### {langName} ~ {Code_FeatureName} ~ Example

<ALLOWED_PREAMBLE_TEXT/>

```{langName}
full clean grammar code example
```

</CLONABLE_STRUCTURE>

</COPY_ADAPTING>

</INCLUDED_SECTION>
