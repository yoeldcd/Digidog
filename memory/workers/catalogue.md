<!-- Authorized: root -->
# Worker Profile Catalogue

Use this index as the orchestrator's authoritative routing catalogue EVICTING read full asigned profile entry.

1. Select the profile more aligned to the task based on it desription, without read it contract.
2. Asignt to spawned subagent the profile filling instruct template above. More subagents in different task can use the same profile. Do not share general task information to workers, **ONLY TELL IT SPECTED CONTRIBUTION**.

## Python

- For tasks like (Python architecture inspection, defect localization, dependency tracing, or evidence-backed code audits) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.python.python_auditor`. Profile Scope: named Python modules and symbols; operation: read-only audit with findings and evidence.
- For tasks like (bounded Python implementation, exact-text code changes, import migrations, or focused test repairs) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.python.python_writer`. Profile Scope: explicitly authorized Python files; operation: Brain `apply-patch` edits plus focused validation.
- For tasks like (behavior-preserving readability cleanup, typing precision, PEP 257 repair, vertical-flow cleanup, or removing dense Python expressions) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.python.python_code_cleaner`. Profile Scope: exactly one authorized Python production file in its entirety, including untouched legacy regions; operation: whole-file Brain-only sanitation with complete defect inventory, structural quality gates, invariant audit, and focused validation.
- For tasks like (enriching Python docstrings explanations, adding domain inline # comments before control flow blocks, or improving code documentation without altering behavior) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.python.python_documentator`. Profile Scope: explicitly authorized Python files; operation: Brain `apply-patch` docstring and comment enrichment plus compilation, quality evaluator, and test validation.
- For tasks like (reviewing a Python patch, checking typing and docstrings, verifying architectural boundaries, or assessing regression risk) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.python.python_reviewer`. Profile Scope: named Python diff and related contracts; operation: read-only review with acceptance risks and evidence.

### PyQt

- For tasks like (editing PyQt widgets, signals and slots, layouts, window behavior, or Qt-specific presentation adapters) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.python.pyqt.python_pyqt_writer`. Profile Scope: explicitly authorized PyQt presentation files; operation: Brain `apply-patch` edits plus focused Qt validation.

## JavaScript

- For tasks like (JavaScript runtime-flow tracing, DOM behavior audits, dependency inspection, or defect localization) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.javascript.javascript_auditor`. Profile Scope: named JavaScript modules and browser/runtime boundaries; operation: read-only audit with findings and evidence.
- For tasks like (bounded JavaScript implementation, module refactors, event-handler changes, or focused test repairs) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.javascript.javascript_writer`. Profile Scope: explicitly authorized JavaScript files; operation: Brain `apply-patch` edits plus focused validation.
- For tasks like (reviewing JavaScript changes, checking module boundaries, validating behavior preservation, or assessing regression risk) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.javascript.javascript_reviewer`. Profile Scope: named JavaScript diff and related contracts; operation: read-only review with acceptance risks and evidence.

## TypeScript

- For tasks like (TypeScript contract tracing, type-safety audits, dependency analysis, or defect localization) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.typescript.typescript_auditor`. Profile Scope: named TypeScript modules and type contracts; operation: read-only audit with findings and evidence.
- For tasks like (bounded TypeScript implementation, typed API changes, component or service refactors, or focused test repairs) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.typescript.typescript_writer`. Profile Scope: explicitly authorized TypeScript files; operation: Brain `apply-patch` edits plus focused validation.
- For tasks like (enriching TypeScript TSDoc or JSDoc, documenting exported contracts, clarifying asynchronous effects and failure behavior, or adding non-obvious domain invariant comments without changing behavior) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.typescript.typescript_documentator`. Profile Scope: explicitly authorized TypeScript files; operation: documentation-only Brain `apply-patch` edits plus typecheck, focused tests, quality evaluator, and comment-only diff validation.
- For tasks like (reviewing TypeScript patches, checking type contracts, validating dependency direction, or assessing regression risk) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.typescript.typescript_reviewer`. Profile Scope: named TypeScript diff and related contracts; operation: read-only review with acceptance risks and evidence.

## Markdown

- For tasks like (bounded Markdown editing, literal section synchronization, heading-preserving documentation changes, or focused formatting repairs) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.markdown.markdown_document_editor`. Profile Scope: explicitly authorized Markdown files and source templates; operation: atomic exact-text or structural patches plus scoped Markdown validation.

## PowerShell

- For tasks like (bounded PowerShell script or module edits, parameter-contract changes, pipeline repairs, error-handling changes, or focused Pester test repairs) instruct the worker to run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.powershell.powershell_editor`. Profile Scope: explicitly authorized PowerShell scripts, modules, manifests, and tests; operation: Core Brain `apply-patch` edits plus parser, analyzer, focused test, runtime, and scoped-diff validation.

---

## Work Delegation Instruct

Instruct your workers filling strictelly the `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.worker_instructing_template`.

---

## Creating specialized profile

IF this index don't include an profile aligned to handled task. Make an new profile that cover task boundaries. Follow next steeps to do:

1. Read `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.worker_design.worker_design_template`.
2. Append the worker profile `py {LOCAL_BRAIN_SCRIPT} add-memory-entry workers.{langName}.[{domain}].{worker_name}`
3. Registre the new worker on this catalogue in specific head level, following item template `- For tasks like {Uses Cases separated by conma}, instruct to worker run:`+`py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.{lang_name}.{lang_name}_{role}/`+`Scope: {A summary of profile boundaries}`

The workers naming policies declares template `{lang_name}_{specialization}.md` for semantic-fast finding.
The created profiles need to be reusable out of your workspace, never include absolutes.

APPEND ONLY REUSABLE PROFILES
