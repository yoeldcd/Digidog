# Entity Detection Stage

## System Prompt

Return only valid JSON matching the requested KnowledgeDeltaDTO shape. Extract specific semantic entity names, class-definition entities, and short descriptions.

## Stage Objective

Detect the main named objects, contracts, commands, processes, modules, rules, data stores, configuration objects, and reusable concepts present in the content.

## Stage Output Policy

- Return entities only; relations must be an empty array.
- Reuse ENTITY_CLASS_CATALOG class names when they fit the detected object family.
- For each newly discovered subtype, include one `CLS` entity defining that subtype.
- A `CLS` canonical_name must be PascalCase and must name a reusable type, not one specific object.
- Object entities must use a spaCy base label or `SPACY_BASE.PascalCaseSubtype`.
- Object entities must not use `CLS`.
- Do not emit document-wrapper entities created from the source container, date, title, or heading.
- Entity names are nominal labels. If a word only describes a state, version, role, or quality, put it in description unless it is part of the object's proper signature.
- Do not emit absent base roots; if the catalog does not list a root class, choose a listed agentic base or `MISC.Concept`.
