# Schema Evolution Stage

## System Prompt

Return only valid JSON matching the requested KnowledgeDeltaDTO shape. Propose ontology suggestions only when current classes or predicates are insufficient.

## Stage Objective

Identify missing ontology vocabulary implied by the content.

## Stage Output Policy

- In dream runs, leave schema_suggestions empty unless the caller explicitly enables this stage.
- Prefer `CLS` class-definition entities for class semantics.
- Do not propose SQLite migrations, tables, or columns.
- Do not rewrite existing class definitions when a new object can reuse them.
