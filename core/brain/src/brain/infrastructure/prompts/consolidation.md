# Consolidation Stage

## System Prompt

Return only valid JSON matching the requested KnowledgeDeltaDTO shape. Propose stable claims or reusable patterns only when they are strongly supported.

## Stage Objective

Identify stable knowledge that can be consolidated without losing source-level nuance.

## Stage Output Policy

- Keep proposals source-grounded and conservative.
- Do not overwrite contradictions; use contested or supersedes semantics when needed.
- Do not summarize the whole source as one entity.
- Return empty arrays when the content only supports episodic or isolated observations.
