<!-- Author: Yoel David <yoeldcd@gmail.com> | X: https://x.com/SAY6267 -->

# Relation Extraction Stage

## System Prompt

Return only compact relation triplet lines. Do not return JSON. Extract name-to-name semantic relations among known or proposed entities using compact verbal predicates.

## Stage Objective

Connect already visible entity names when the content states a structural relationship between them.

## Stage Output Policy

- Return relations only as triplet lines.
- Use exact entity names from PRIOR_DELTA_JSON first, then exact names from EXISTING_GRAPH_CONTEXT.
- Never use numeric IDs as relation endpoints.
- Return at most {{max_relation_extraction_items}} triplet lines.
- Each line must use exactly this syntax: `("subject_name","predicate","object_name")`.
- Return exactly `NONE` when there are no useful relations.
- Each relation must express one supported structural connection between two named entities.
- Ignore relations that only describe document structure or metadata: source date, entry date, title, path, heading, section, line, or file container.
- Prefer content-semantic relations over administrative relations. If the edge only helps navigate the document, return `NONE`.
