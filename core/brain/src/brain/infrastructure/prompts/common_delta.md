# Knowledge Delta Prompt

{{response_format_summary}}

## Stage Objective

{{stage_objective}}

## Stage Output Policy

{{stage_output_policy}}

## Ontology Policy

- This is open-world subtype discovery over a stable spaCy-compatible base classifier.
- Object entities use `EntityDTO.entity_class` as one spaCy base class or `SPACY_BASE.PascalCaseSubtype`.
- Class-definition entities use `entity_class` as `CLS` and `canonical_name` as the PascalCase subtype name only.
- `CLS` names are programmatic class names, not names of specific people, files, commands, documents, projects, artifacts, or source objects.
- A discovered subtype is valid only when a matching `CLS` entity exists in the same delta or in `ENTITY_CLASS_CATALOG`.
- Use `MISC.Concept` only when no better spaCy base or registered subtype fits.
- Use only base classes from ENTITY_CLASS_CATALOG. Do not invent spaCy roots that are absent from the catalog.
- Built-in fallback predicates are only: mentions, describes, supports, contradicts, supersedes, related_to.
- Any semantic predicate beyond those primitives must be discovered from source evidence and expressed as a lower snake_case verbal key.
- Do not emit schema_suggestions in dream.

## Rules

- You are not given the source file path or database source ID.
- Do not infer, emit, or mention source_path, source_id, sourceId, file paths, or line ranges.
- Source anchoring is applied deterministically by the local pipeline after your response.
{{response_format_rules}}
- Do not emit aliases.
- Entity names must already be the canonical specific labels.
- For long content, return up to {{max_entity_detection_items}} high-signal entities and up to {{max_relation_extraction_items}} high-signal relations. This is a hard limit, not a target.
- Entities are semantic object labels discovered from content, not summaries.
- Entity canonical_name values must be compact object labels, not copied sentences, instructions, or clauses.
- Entity canonical_name values must be nominal identifiers. Do not put non-signature adjectives in the name; move them to description instead.
- Keep adjectives in canonical_name only when they are part of a proper-name signature or technical identifier.
- Do not create entities for source wrappers, document titles generated from dates, headings, file containers, line numbers, or timestamps unless the content itself discusses them as semantic objects.
- Keep entity labels under 8 words and prefer named noun phrases.
- Put explanatory context in EntityDTO.description only when useful, and keep descriptions under 24 words.
- EntityDTO shape is only: id, entity_class, canonical_name, description, confidence.
- subject_name and object_name must exactly match canonical_name values visible in PRIOR_DELTA_JSON or EXISTING_GRAPH_CONTEXT.
- Do not emit endpoint ID fields, numeric IDs, literal paths, evidence quotes, or new entity names inside relations.
- Predicate values must be lower snake_case verbal nuclei.
- Predicate values must not contain subject names, object names, entity classes, file names, or noun phrases pretending to be relations.
- Prefer diverse precise predicates; avoid generic describes, defines, or uses unless that verb is exactly the relation.
- For relation extraction, do not enumerate repetitive term catalogs.
- Do not emit source-structure relations such as date, title, path, heading, section, line, or file-container relations.
- Keep only content-semantic edges that explain procedures, requirements, ownership, dependency, inclusion, configuration, validation, transformation, causality, agreement, or contradiction.
- Use confidence between 0 and 1.
- Do not invent secrets or private identifiers.
- If the stage has nothing useful to add, return empty arrays.
- Do not perform consolidation, profile synthesis, or broad summary generation unless this exact stage asks for it.

## Existing Graph Context

{{graph_context}}

## Entity Class Catalog

{{classifier_catalog}}

## Prior Delta JSON

{{prior_delta_json}}

## Content

{{content}}
