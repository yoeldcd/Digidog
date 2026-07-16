<!-- Author: Yoel David <yoeldcd@gmail.com> | X: https://x.com/SAY6267 -->

# Deduplication Stage

## System Prompt

Return only valid JSON matching the requested KnowledgeDeltaDTO shape. Propose supersedes relations for duplicate or near-duplicate concepts.

## Stage Objective

Detect semantic duplicates among visible graph objects.

## Stage Output Policy

- Prefer relations that preserve history instead of deleting or overwriting records.
- Use exact endpoint names from PRIOR_DELTA_JSON or EXISTING_GRAPH_CONTEXT.
- Do not invent new entity names.
- Return empty arrays when duplicates are uncertain.
