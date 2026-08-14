<!-- Authorized: root -->
<!-- 

Fill this template with worker specific task boundaies.
Inlcue only the specific worker contribuiting details, but NEVER the general task background.

- DONT VIOLATE TEMPLATE FORMAT!!!
- DO NOT COPY THIS COMMENTARY
- DO NOT SUMMARIZE or COMPACT THIS STRUCTURE

-->

# Work Assignment ~ {name}

Before executing any task actions execute the command `py {LOCAL_BRAIN_SCRIPT} get-memory-entry workers.<ENTRY_PATH> --authority workers.<ENTRY_PATH>` with elevated shell permissions request and follow readed worker contract instructions.

## 1. Objective & Deliverables

- **Primary goal**: <CONCRETE_GOAL_DESCRIPTION>
- **Expected deliverable**: <OBSERVABLE_ARTIFACT_OR_FINDINGS_DELIVERABLE>

### Requirement Matrix
<!-- 
Provide one concrete row for every independently verifiable requirement. Do not leave generic labels, merged requirements, missing evidence, or validation commands for the worker to infer.
-->

| ID | Authorized location | Evidence before | Required resolution | Invariants | Validation gate |
| --- | --- | --- | --- | --- | --- |
| REQ-01 | <EXACT_FILE_PATH_AND_SYMBOL_OR_SECTION> | <CURRENT_OBSERVABLE_STATE> | <ONE_OBSERVABLE_REQUIRED_OUTCOME> | <BEHAVIOR_OR_CONTENT_THAT_MUST_NOT_CHANGE> | <EXACT_COMMAND_AND_PASS_CONDITION> |

## 1. Domain & Authorized Profile Scope

- Target domain path: `<TARGET_DOMAIN_PATH_OR_MODULES>`
- Parent authorization: `<EXPLICIT_AUTHORITY_FOR_THIS_ATOMIC_CONTRIBUTION>`
- Primary read context: `<COMMA_SEPARATED_FILES_OR_DIRECTORIES_ALREADY_KNOWN_TO_BE_RELEVANT>`
- Authorized write files: `<COMMA_SEPARATED_ALLOWED_FILES>`
- Prohibited paths: `<PROHIBITED_PATHS_OR_ACTIONS>`
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
