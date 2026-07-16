<!-- Author: Yoel David <yoeldcd@gmail.com> | X: https://x.com/SAY6267 -->

# Brain Design Patterns

## Index:
- [Overview](#overview)
- [Core Patterns](#core-patterns)
- [Anti-Patterns](#anti-patterns)

## Overview:
Brain patterns protect the separation between local authored memory, private graph state, external model
generation, deterministic validation, and user-facing CLI behavior. The key principle is that flexible discovery
is allowed, but durable state changes must pass explicit contracts.

## Core Patterns:

## `brain.open-world-kg`

### Pattern Category
Knowledge graph schema evolution.

#### Evidence-Backed Open-World Ontology

The graph starts with a spaCy-compatible classifier spine and then discovers semantic subtypes and relation types
from source evidence. This avoids hardcoding a personal or domain-specific taxonomy into reusable tooling while
still preventing every document from inventing incompatible names for the same kind of entity.

Entity classes use `CLS`, a base spaCy label, or `SPACY_BASE.PascalCaseSubtype`. When NER discovers a subtype, the
delta also contains a `CLS` entity whose canonical name is the PascalCase subtype name and whose description
explains its semantics. The `entity_classes` table materializes accepted `CLS` entities as a cache for prompts and
validation. During one dream cycle, the runner also keeps accepted `CLS` entities in a run-local catalog so later
sources can reuse newly declared classifiers before persistence. Schema suggestions are data rows, not migrations.

### Anti-Patterns:
- Do not hardcode local people, projects, or relationship labels into extraction logic.
- Do not force unknown subjects into a fixed domain taxonomy when evidence suggests a new class.
- Do not let schema suggestions create SQLite tables or alter migrations automatically.

### Implementation Examples:

```python
entity_class = canonical_entity_class(raw_class)
predicate = canonical_relation_type(raw_predicate)
```

## `brain.llm-proposal-boundary`

### Pattern Category
External model integration.

#### LLM As Advisory Delta Producer

External model stages propose specific entities and name-to-name relations, but they cannot write to the
repository. The LLM does not propose aliases. Relation extraction emits exact endpoint names and verbal predicate
nuclei; the harness resolves those names into `RelationDTO` endpoint IDs before deterministic validation and
reviewed application can persist accepted records.

Entity detection is expected to discover meaningful object labels across the whole framed source. It receives a
classifier catalog containing spaCy base labels and known discovered subtypes. It should reuse an existing subtype
when it fits, and create a new `SPACY_BASE.PascalCaseSubtype` only when the text introduces a distinguishable
class. The fallback `MISC.Concept` class is reserved for truly generic ideas, not as a universal bucket for every
extracted label.

The model is never asked to invent or reuse numeric IDs. After entity detection returns canonical names, the
harness assigns large positive candidate IDs that exist only inside the pending delta. Relation extraction then
sees the same entity names, not those IDs, and the sanitizer converts exact `subject_name` and `object_name`
matches into the local candidate IDs needed by `RelationDTO`.

When an entity-detection delta introduces `CLS` entities, validation processes those class-definition entities
before dependent objects. The dream runner also adds validated `CLS` names to the same-cycle classifier catalog,
so the next source frame can reuse the class without waiting for a separate apply step.

Merge and consolidation stages do not need a separate classifier dictionary. At that point the classifier is
implicit in the entities themselves, especially in `CLS` nodes and the entity classes already attached to objects.

Relation extraction is capped at 24 high-signal edges per stage call, and only 24 prior entity names are shown to
that stage. That cap preserves useful structure from long sources while keeping model JSON small enough to parse
reliably in the CLI pipeline.

This pattern keeps generative flexibility while preserving predictable local state.

### Anti-Patterns:
- Do not pass raw model JSON directly into repository writes.
- Do not use a successful model response as proof that evidence exists.
- Do not accept copied sentences as entity canonical names. Compact technical artifact names with file extensions
  are labels, not sentences, when they identify an actual object.
- Do not ask the model to use numeric relation endpoint IDs.
- Do not treat model schema evolution output as a migration instruction.

### Implementation Examples:

```python
delta = generate_delta_with_llm(stage_name, source_path, content, prior_delta)
report = validate_delta(delta, source_content=content, minimum_confidence=0.65)
```

## `brain.repository-boundary`

### Pattern Category
Persistence ownership.

#### Repository Owns SQLite Writes

SQLite access is centralized behind `KnowledgeRepository`. Higher layers request source, evidence, entity,
relation, schema suggestion, delta, and dream run writes through repository methods.

The repository initializes schema idempotently and refreshes graph-search rows when persisted entities or evidence
change.

### Anti-Patterns:
- Do not open ad hoc SQLite connections in command actions.
- Do not duplicate upsert rules outside the repository.
- Do not let command actions compose SQL for graph persistence.

### Implementation Examples:

```python
repository = KnowledgeRepository()
entity_id = repository.upsert_entity(entity_dto)
relation_id = repository.upsert_relation(relation_dto)
```

## `brain.scoped-knowledge-runtime`

### Pattern Category
Persistence isolation.

#### One Config, Two Graph Stores

The knowledge system has two physical SQLite databases with the same schema. The global database stores
cross-workspace knowledge derived from shared memory, diary, and profiles. The local database stores knowledge
derived from the active workspace, especially workspace logs. Both databases read the same global config file for
model stages, thresholds, and endpoint settings.

This pattern lets the brain combine global continuity with local project context without forcing either corpus to
pollute the other. Query defaults can read both scopes, while write workflows such as dream, delta review, and
delta deletion operate on one explicit writable scope at a time.

### Anti-Patterns:
- Do not create a second config file under the local workspace graph runtime.
- Do not merge global and local SQLite IDs into one unqualified mutation command.
- Do not ingest workspace logs into the global graph.

### Implementation Examples:

```python
global_repository = KnowledgeRepository(scope="global")
local_repository = KnowledgeRepository(scope="local")
```

## `brain.global-query`

### Pattern Category
Retrieval interface design.

#### Single Consultation Point

The global `query` command is the stable retrieval interface for the brain. Source and mechanism flags select
which backends run; users should not need separate top-level search commands for graph, vector, and direct text
retrieval.

The global query service returns one normalized DTO shape so callers can combine results and warnings without
backend-specific parsing. Knowledge results include the producing graph scope so callers can distinguish global
continuity from workspace-local context.

### Anti-Patterns:
- Do not reintroduce a separate direct memory search command.
- Do not make callers choose storage internals before asking a question.
- Do not fail the entire query when one optional backend is unavailable.

### Implementation Examples:

```python
results = query_global(
    text="schema evolution",
    source="all",
    mechanism="all",
    knowledge_scope="all",
    limit=5,
)
```

## `brain.proposal-review-first`

### Pattern Category
Safe cognitive consolidation.

#### Reviewable Dream Runs

The `dream` command always starts by generating and persisting proposed deltas with validation reports. It then
prints proposals indexed by their persisted delta IDs and applies only the applicable deltas selected with `y` or
a comma-separated ID list such as `48,52`. The one exception is an empty scoped graph in human output mode: when
no entities or relations exist yet, `dream` treats valid first-run deltas as a bootstrap and applies them
automatically after deterministic validation.

The review renderer avoids generic `key=value` dumps. It groups records by state, source, proposal counts,
rationale, entities, relations, schema suggestions, and validation messages. Live text content is always quoted;
when terminal color is enabled, those live strings render in blue while states, procedures, schema tokens, metrics,
and warnings use pragmatic role colors.

This pattern makes graph evolution auditable and keeps contradictions visible rather than overwritten.

### Anti-Patterns:
- Do not write dream proposals before the user has reviewed the ID-indexed deltas, except for the documented
human-mode empty-graph bootstrap path.
- Do not overwrite contested facts silently.
- Do not delete old graph history when a newer relation supersedes an older one.

### Implementation Examples:

```python
runner = DreamRunner(repository=repository)
run = runner.run(domain="memory", dry_run=True, use_llm=True)
pending_rows = [
    repository.get_pending_delta(delta_id=delta_id)
    for delta_id in run.pending_delta_ids
]
```

## `brain.graph-context-linking`

### Pattern Category
Cross-source graph linking.

#### Source-Local Extraction With Global Context

Each LLM stage receives the immediate source text plus a compact read-only graph context containing persisted
entity names and persisted relations. The model may create local entities for the current source, and relation
extraction may connect either current-source names or already-known graph names when the source establishes a
connection to them. The model never uses numeric endpoint IDs.

This means foreign interrelations require stable canonical names. In human output mode, the first dream cycle over
an empty graph discovers labels and schema vocabulary, then automatically applies valid bootstrap deltas so the
graph has canonical names for later passes. Within a dry-run or JSON pass, validated `CLS` names still propagate
through the run-local classifier catalog, but object names from unapplied deltas are not exposed as cross-source
entity IDs. The harness keeps a hidden exact-name resolver so a model endpoint name such as Query Command becomes
an internal entity ID only when that name exists.

### Anti-Patterns:
- Do not let a relation point to a raw sentence, path, or literal text object.
- Do not ask the model to link pending, unapplied local IDs across separate source deltas.
- Do not accept a relation whose endpoint name cannot be resolved to a current or persisted entity.
- Do not invent foreign edges when neither the current source nor the persisted graph context supports them.

### Implementation Examples:

```python
graph_context = runner._build_graph_context()
stage_deltas, warnings = generate_multistage_deltas(
    source_path=source.path,
    content=content,
    base_delta=base_delta,
    graph_context=graph_context,
    entity_name_to_id=runner._build_entity_resolution_context(),
)
```

## `brain.semantic-frame-harness`

### Pattern Category
Model input preparation.

#### Harness Owns Provenance, LLM Reads Knowledge Frames

The LLM must not reason over files, paths, database IDs, or source identity. The harness reads raw Markdown, diary,
profile, and log content, parses it into a semantic knowledge frame, and sends only that frame text plus compact
graph context to model stages. Source provenance remains local metadata used for persistence, validation, logs,
and review.

This pattern keeps model work aligned with the task it performs best: reading text and proposing semantic
entities or relations. File paths, source IDs, timestamps, and ingestion state are abstractions owned by the local
runtime.

### Anti-Patterns:
- Do not include source paths, source IDs, or line ranges in the prompt body.
- Do not ask the model to decide where a fact is stored.
- Do not send raw log templates when the harness can parse them into change records.

### Implementation Examples:

```python
frame = build_knowledge_frame(source_dto=source, content=raw_content)
model_text = render_knowledge_frame_for_llm(frame_dto=frame)
```

## Anti-Patterns:

### `brain.search-command-split`

Separate top-level search commands for graph, vector, and text lookup make the command surface harder to teach and
cause duplicated filtering behavior. Use the global query command with source and mechanism selectors.

### `brain.fixed-domain-extraction`

Extraction logic must not encode one personal ontology as the default. Generic source analysis should discover
classes and predicates from evidence and let the ontology registry store them.

### `brain.model-owned-state`

External model output must never own persistent state. Models can propose; validators and repositories decide.

### `brain.infrastructure.runtime-in-repo`

Private graph runtime files must not be committed. The source package is versioned, while the runtime database and
config stay under ignored local state.
