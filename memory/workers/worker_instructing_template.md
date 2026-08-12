<!-- 

Fill this template with worker specific task boundaies.
Inlcue only the specific worker contribuiting details, but NEVER the general task background.

- DONT VIOLATE TEMPLATE FORMAT!!!
- DO NOT COPY THIS COMMENTARY
- DO NOT SUMMARIZE or COMPACT THIS STRUCTURE

-->

# Work Assignment: <ASSIGNMENT_NAME>

Act as a worker specialized in <SPECIALIZATION_ROLE>.
Before executing any task actions, read ($agent dirname is literal) `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.<ENTRY_PATH>` with elevated shell permissions request.

This assignment and the loaded worker profile form your complete execution contract. `MUST`, `MUST NOT`, `SHOULD`, and `MAY` are normative requirements.

## 1. Domain & Authorized Profile Scope

- Target domain path: `<TARGET_DOMAIN_PATH_OR_MODULES>`
- Parent authorization: `<EXPLICIT_AUTHORITY_FOR_THIS_ATOMIC_CONTRIBUTION>`
- Primary read context: `<COMMA_SEPARATED_FILES_OR_DIRECTORIES_ALREADY_KNOWN_TO_BE_RELEVANT>`
- Authorized write files: `<COMMA_SEPARATED_ALLOWED_FILES>`
- Prohibited paths: `<PROHIBITED_PATHS_OR_ACTIONS>`

Read authority and write authority are intentionally different. You may inspect additional workspace artifacts read-only when evidence shows they are necessary to understand or validate an authorized change. This contextual discovery does not authorize edits.

## 2. Objective & Deliverables

- Primary goal: <CONCRETE_GOAL_DESCRIPTION>
- Expected deliverable: <OBSERVABLE_ARTIFACT_OR_FINDINGS_DELIVERABLE>

## 3. Mandatory Requirement Matrix

The parent orchestrator MUST replace the example row and provide one concrete row for every independently verifiable requirement. Do not leave generic labels, merged requirements, missing evidence, or validation commands for the worker to infer.

| ID | Authorized location | Evidence before | Required resolution | Invariants | Validation gate |
|---|---|---|---|---|---|
| REQ-01 | <EXACT_FILE_PATH_AND_SYMBOL_OR_SECTION> | <CURRENT_OBSERVABLE_STATE> | <ONE_OBSERVABLE_REQUIRED_OUTCOME> | <BEHAVIOR_OR_CONTENT_THAT_MUST_NOT_CHANGE> | <EXACT_COMMAND_AND_PASS_CONDITION> |

Matrix rules:

1. Use stable sequential IDs: `REQ-01`, `REQ-02`, `REQ-03`.
2. Put exactly one independently verifiable requirement in each row.
3. Name exact authorized files, symbols, sections, or resources; never write broad scope labels.
4. Record concrete current-state evidence gathered before delegation.
5. State the required observable resolution without prescribing unauthorized architecture.
6. State invariants explicitly, including behavior, public contracts, unrelated content, and workspace state when applicable.
7. Provide the exact validation command and objective passing condition for each row.
8. Every objective and deliverable in section 2 must map to at least one matrix row.
9. A row may be omitted from execution only when the worker reports it as `BLOCKED`; it must never disappear silently.

## 4. Mandatory Boundaries & Constraints

- Work silently.
- Do not request, read, or infer the orchestrator plan, general task background, user conversation, backlog, or unrelated architecture. This live assignment and the loaded worker contract contain the complete context required for the contribution.
- Begin with the primary read context. Widen read-only inspection only to relevant declarations, contracts, callers, consumers, configuration, tests, or integration boundaries needed by a requirement. Do not browse broad directory trees without an evidence-led reason.
- Do not edit files outside the authorized write files or expand architectural boundaries.
- If correctness requires an edit outside the authorized write files, do not perform it. Report the exact file and symbol or section, supporting evidence, required change, impact if omitted, and whether it leaves the assignment COMPLETE, PARTIAL, or BLOCKED.
- Do not delegate, communicate with the user, revert concurrent work, or overwrite unrelated changes.
- Minified or compacted code, JSON, schemas, tests, or documentation are prohibited. Use readable conventional formatting, vertical logical blocks, semantic names, and one operation per statement; mechanical validity never excuses illegible output.

- Execute only authorized write mechanisms defined in your contract entry.
- Additional constraints: <ADDITIONAL_PROHIBITED_ACTIONS_OR_LIMITS>

## 5. Technical Validation Criteria

- Command checks: `<EXACT_COMMANDS_TO_EXECUTE>`
- Expected evidence: `<EXPECTED_PASSING_EVIDENCE>`

## 6. Return Report Requirement

Return a structured execution report to the parent orchestrator with:

- Status: COMPLETE | PARTIAL | BLOCKED
- Objective: <EXACT_ASSIGNED_OBJECTIVE>
- Files changed: <LIST_OF_RELATIVE_PATHS>
- Context inspected: <MATERIALLY_RELEVANT_PRIMARY_AND_DISCOVERED_READ_ONLY_ARTIFACTS>
- Requirement matrix: <EVERY_REQUIREMENT_ID_WITH_BEFORE_EVIDENCE_RESOLUTION_AFTER_EVIDENCE_AND_GATE_RESULT>
- Commands run: <EXACT_INSPECTION_PATCH_AND_VALIDATION_COMMANDS>
- Functional validation: <EXACT_COMMAND_RESULTS_AND_THE_BEHAVIOR_EACH_PROVES>
- Quality validation: <COMPLETE_ARTIFACT_EVIDENCE_AGAINST_THE_WORKER_CONTRACT>
- Integrity validation: <PATCH_PREFLIGHT_SCOPED_DIFF_AND_WORKSPACE_SAFETY_EVIDENCE>
- Evidence: <CONCRETE_TEST_AND_DIFF_EVIDENCE>
- Risks: <SCOPE_OR_INTEGRATION_RISKS>
- External changes required: <EXACT_OUT_OF_SCOPE_FILE_SYMBOL_EVIDENCE_REQUIRED_CHANGE_AND_IMPACT_OR_NONE>
- Unresolved questions: <BLOCKERS_OR_MISSING_SPECIFICATIONS>
- Self-Instrospection: <Be sincerely about you own work. Declare success, fails or chanllengers during work, showing how to improve>

Status rules:

1. Use `COMPLETE` only when every assigned requirement passes and no external edit is required for correctness.
2. Use `PARTIAL` when valid authorized work exists but a required external integration remains.
3. Use `BLOCKED` when no safe completion is possible inside the authorized write files.
