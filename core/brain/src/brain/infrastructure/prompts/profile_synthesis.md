<!-- Author: Yoel David <yoeldcd@gmail.com> | X: https://x.com/SAY6267 -->

# Profile Synthesis Stage

## System Prompt

Return only valid JSON matching the requested KnowledgeDeltaDTO shape. Synthesize stable long-lived facts using discovered ontology classes.

## Stage Objective

Extract durable profile-level knowledge only when the content clearly supports it.

## Stage Output Policy

- Prefer stable preferences, constraints, methods, and recurring roles over episodic details.
- Do not infer identity facts beyond the content.
- Reuse existing class definitions when available.
- Return empty arrays when the source does not support long-lived profile knowledge.
