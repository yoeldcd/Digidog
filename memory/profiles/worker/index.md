# Worker Profile Index

Use this index as the orchestrator's authoritative routing catalogue.

1. Select the profile more aligned to the task based on it desription, without read it contract.
2. Asignt to spawned subagent the profile filling instruct template above. More subagents in different task can use the same profile. Do not share general task information to workers, **ONLY TELL IT SPECTED CONTRIBUTION**.

## Python

- For tasks like (Python architecture inspection, defect localization, dependency tracing, or evidence-backed code audits) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry profiles.worker.python.python_auditor`. Profile Scope: named Python modules and symbols; operation: read-only audit with findings and evidence.
- For tasks like (bounded Python implementation, exact-text code changes, import migrations, or focused test repairs) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry profiles.worker.python.python_editor`. Profile Scope: explicitly authorized Python files; operation: Brain `apply-patch` edits plus focused validation.
- For tasks like (behavior-preserving readability cleanup, typing precision, PEP 257 repair, vertical-flow cleanup, or removing dense Python expressions) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry profiles.worker.python.python_code_cleaner`. Profile Scope: exactly one authorized Python production file in its entirety, including untouched legacy regions; operation: whole-file Brain-only sanitation with complete defect inventory, structural quality gates, invariant audit, and focused validation.
- For tasks like (reviewing a Python patch, checking typing and docstrings, verifying architectural boundaries, or assessing regression risk) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry profiles.worker.python.python_reviewer`. Profile Scope: named Python diff and related contracts; operation: read-only review with acceptance risks and evidence.

### PyQt

- For tasks like (editing PyQt widgets, signals and slots, layouts, window behavior, or Qt-specific presentation adapters) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry profiles.worker.python.pyqt.python_pyqt_editor`. Profile Scope: explicitly authorized PyQt presentation files; operation: Brain `apply-patch` edits plus focused Qt validation.

## JavaScript

- For tasks like (JavaScript runtime-flow tracing, DOM behavior audits, dependency inspection, or defect localization) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry profiles.worker.javascript.javascript_auditor`. Profile Scope: named JavaScript modules and browser/runtime boundaries; operation: read-only audit with findings and evidence.
- For tasks like (bounded JavaScript implementation, module refactors, event-handler changes, or focused test repairs) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry profiles.worker.javascript.javascript_editor`. Profile Scope: explicitly authorized JavaScript files; operation: Brain `apply-patch` edits plus focused validation.
- For tasks like (reviewing JavaScript changes, checking module boundaries, validating behavior preservation, or assessing regression risk) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry profiles.worker.javascript.javascript_reviewer`. Profile Scope: named JavaScript diff and related contracts; operation: read-only review with acceptance risks and evidence.

## TypeScript

- For tasks like (TypeScript contract tracing, type-safety audits, dependency analysis, or defect localization) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry profiles.worker.typescript.typescript_auditor`. Profile Scope: named TypeScript modules and type contracts; operation: read-only audit with findings and evidence.
- For tasks like (bounded TypeScript implementation, typed API changes, component or service refactors, or focused test repairs) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry profiles.worker.typescript.typescript_editor`. Profile Scope: explicitly authorized TypeScript files; operation: Brain `apply-patch` edits plus focused validation.
- For tasks like (reviewing TypeScript patches, checking type contracts, validating dependency direction, or assessing regression risk) instruct to worker run `py {LOCAL_BRAIN_SCRIPT} get-memory-entry profiles.worker.typescript.typescript_reviewer`. Profile Scope: named TypeScript diff and related contracts; operation: read-only review with acceptance risks and evidence.

---

## Worker orientation prompt template

**IMPORTANT**: DONT VIOLATE THIS TEMPLATE FORMAT!!!

Redact worker instructions following next template:
Do not share general task information to workers, **ONLY TELL IT SPECTED CONTRIBUTION**.

```markdown
# Work Assignment: <ASSIGNMENT_NAME>

Act as a worker specialized in <SPECIALIZATION_ROLE>.
Before executing any task actions, read: `py {LOCAL_BRAIN_SCRIPT} get-memory-entry profiles.worker.<ENTRY_PATH> --json` with elevated shell permissions request.

## 1. Domain & Authorized Profile Scope
- Target domain path: `<TARGET_DOMAIN_PATH_OR_MODULES>`
- Authorized write files: `<COMMA_SEPARATED_ALLOWED_FILES>`
- Prohibited paths: `<PROHIBITED_PATHS_OR_ACTIONS>`

## 2. Objective & Deliverables
- Primary goal: <CONCRETE_GOAL_DESCRIPTION>
- Expected deliverable: <OBSERVABLE_ARTIFACT_OR_FINDINGS_DELIVERABLE>

## 3. Mandatory Boundaries & Constraints
- Work silently.
- Do not edit files outside authorized Profile Scope or expand architectural boundaries.
- Execute only authorized write mechanisms defined in your contract entry.
- Additional constraints: <ADDITIONAL_PROHIBITED_ACTIONS_OR_LIMITS>

## 4. Technical Validation Criteria
- Command checks: `<EXACT_COMMANDS_TO_EXECUTE>`
- Expected evidence: `<EXPECTED_PASSING_EVIDENCE>`

## 5. Return Report Requirement
Return a structured execution report to the parent orchestrator with:
- Status: COMPLETE | PARTIAL | BLOCKED
- Objective: <EXACT_ASSIGNED_OBJECTIVE>
- Files changed: <LIST_OF_RELATIVE_PATHS>
- Commands run: <EXACT_INSPECTION_PATCH_AND_VALIDATION_COMMANDS>
- Evidence: <CONCRETE_TEST_AND_DIFF_EVIDENCE>
- Risks: <SCOPE_OR_INTEGRATION_RISKS>
- Unresolved questions: <BLOCKERS_OR_MISSING_SPECIFICATIONS>
- Self-Instrospection: <Be sincerely about you own work. Declare success, fails or chanllengers during work, showing how to improve>
```

## Instructions for create an new specialized profile

When the task on your hand require a Profile Scoped worker profile that is not cover on this index, you can append a new worker profile specialized on the task boundaries:

1. Read `py {LOCAL_BRAIN_SCRIPT} get-memory-entry profiles.worker.worker_design.worker_design_template`.
2. Append the worker profile `py  {LOCAL_BRAIN_SCRIPT} add-memory-entry profiles.workers.{langName}.[{domain}].{worker_name}`
3. Registre the new worker here on specific head level, following item template `- For tasks like {Uses Cases separated by conma}, instruct to worker run:`+`py {LOCAL_BRAIN_SCRIPT} get-memory-entry profiles.worker.javascript.javascript_reviewer/`+`Scope: {A summary of profile boundaries}`

The workers naming policies declares template `{lang_name}_{specialization}.md` for semantic-fast finding.
The created profiles need to be reusable out of your workspace, never include absolutes.
Dont append a one use only profile.
