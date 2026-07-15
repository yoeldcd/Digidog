# Brain Models & DTOs

## Index:
- [Overview](#overview)
- [Domain Models](#domain-models)
- [Classifier Contract](#classifier-contract)
- [Data Transfer Objects (DTOs)](#data-transfer-objects-dtos)

## Overview:
Brain models are split into three layers. CLI schema dataclasses describe terminal command contracts. Query DTOs
normalize retrieval output across different backends. Knowledge graph Pydantic DTOs validate runtime config,
source records, evidence, entities, relations, graph deltas, validation reports, consolidation decisions, and
dream run summaries.

SQLite table models are documented here as domain models because they define durable graph state. DTO classes are
documented separately because they define Python-side validation and transfer contracts.

## Domain Models:

## `brain.cli-schema`

### Domain Models:

#### `command_registry`

The command registry is the in-memory list of imported command modules. It is not persisted. Each module provides
one command schema and one handler.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| module | Python module | Yes | Imported command module. |
| schema | CommandSchema | Yes | Declarative command metadata. |
| handler | callable | Yes | Function called with parsed arguments. |

## `brain.application.knowledge-sqlite`

### Domain Models:

#### `schema_meta`

Stores schema metadata for idempotent migrations.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| key | text | Yes | Primary key. |
| value | text | Yes | Metadata value, including schema version. |

#### `sources`

Stores stable source identities observed by the knowledge graph inside one physical graph scope. This table is not
an update tracker. File mtimes, lightweight file stats, active source state, processed timestamps, and
changed/deleted source detection live in the scoped `brain_sources.db` registry, so the graph database remains
focused on semantic anchors.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | integer | Yes | Primary key. |
| source_type | text | Yes | Source family such as memory, diary, profiles, or workspace_logs. |
| path | text | Yes | Unique stable path relative to the source root. |
| title | text | No | Human-readable title. |
| active | integer | Yes | One when present, zero when inactive. |

#### `brain_knowledge.db` and `sources.db`

Stores one scoped SQLite knowledge graph. The global graph database lives at `core/database/knowledge/brain_knowledge.db`,
while the local graph database lives at `$agent/database/sources.db`. Both scopes use the same schema and the same
global config file, but their source rows, entity IDs, relation IDs, pending deltas, and dream runs remain
isolated.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| schema_meta | table | Yes | Schema version and migration metadata. |
| sources | table | Yes | Source identity anchors only. |
| entities | table | Yes | Source-anchored graph labels. |
| relations | table | Yes | Source-anchored ID-to-ID graph edges. |
| pending_deltas | table | Yes | Review buffer for model-proposed graph changes. |

#### `brain_sources.db`

Stores current source metadata and per-consumer processed mtimes. The global registry lives at
`core/database/sources/brain_sources.db`; the local workspace registry lives at `$agent/database/brain_sources.db`.
Registry rows are the machine-readable source catalog for memory, diary, profiles, logs, query freshness checks,
dream source selection, and future brain consumers.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| sources.id | integer | Yes | Primary key. |
| sources.scope | text | Yes | Registry scope: global or local. |
| sources.source_type | text | Yes | Source family such as memory, diary, profiles, or workspace_logs. |
| sources.path | text | Yes | Stable source path such as memory/profiles/developer.md or $agent/logs/2026-07/03-07-2026.log.md. |
| sources.title | text | No | Human-readable source title. |
| sources.mtime | real | Yes | Current filesystem modification timestamp. |
| sources.size_label | text | Yes | Human-readable source size captured during registry refresh. |
| sources.line_count_label | text | Yes | Human-readable line count captured during registry refresh. |
| sources.entry_count | integer | Yes | Lightweight heading/list entry count captured during registry refresh. |
| sources.active | integer | Yes | One when the source currently exists, zero when missing. |
| sources.updated_at | real | Yes | Registry update timestamp. |
| source_consumers.id | integer | Yes | Primary key. |
| source_consumers.source_id | integer | Yes | Foreign key to sources. |
| source_consumers.consumer | text | Yes | Consumer namespace such as knowledge_graph. |
| source_consumers.processed_mtime | real | Yes | Last source mtime processed by that consumer. |
| source_consumers.processed_at | real | Yes | Wall-clock timestamp when processing completed. |
| source_consumers.status | text | Yes | Consumer state label, currently processed. |

#### `sources.mtime`

**What It Does:** Stores the current filesystem modification timestamp for one registered source.

**Used By:** Source diff checks before query or dream performs heavier work.

**Contract:** Freshness comparisons use this value against `source_consumers.processed_mtime`. It is updated by
registry refreshes and is never supplied by an external model.

#### `source_consumers`

**What It Does:** Stores per-consumer processing state for registered source rows.

**Used By:** Knowledge graph freshness checks, dream source selection, and future source consumers that need their
own processed mtime.

**Contract:** A source can have multiple consumer rows. This keeps KG processing state independent from other
brain consumers without duplicating source metadata.

#### `source_consumers.consumer`

**What It Does:** Names the consumer namespace that processed a source.

**Used By:** `knowledge_graph` source freshness tracking and future source-processing consumers.

**Contract:** The value is an internal namespace. It should not be treated as model prompt content or source text.

#### `source_consumers.processed_mtime`

**What It Does:** Stores the source mtime last processed by a consumer.

**Used By:** `diff_sources_for_consumer()` when deciding whether a source changed since the previous pass.

**Contract:** If it differs from `sources.mtime`, the source is considered changed for that consumer. Query may
warn about this state; dream may read and process the changed source.

#### `processed_mtime`

**What It Does:** Names the freshness value independently of the table-qualified field name.

**Used By:** DTO references and service documentation that describe consumer freshness generically.

**Contract:** It represents a filesystem mtime, not a wall-clock processing timestamp. Wall-clock audit time lives
in `source_consumers.processed_at`.

#### `source_consumers.processed_at`

**What It Does:** Stores the wall-clock timestamp when a consumer finished processing a source.

**Used By:** Audit views, diagnostics, and future operator-facing freshness reports.

**Contract:** It is not used for change detection. Freshness uses `source_consumers.processed_mtime`; this field
answers when that processing state was written.

#### `$agent/logs/index.md`

Stores the human-readable workspace log summary grouped by domain and subdomain. It is useful for people and
documentation, but it is not used for freshness checks. The local log freshness contract is
`$agent/database/brain_sources.db`.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| heading | Markdown | Yes | Domain or subdomain section rendered from parsed log entries. |
| read command | Markdown code span | Yes | Suggested `read-log` invocation for the latest matching log file. |

#### `evidence`

Stores quoted support text tied to sources.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | integer | Yes | Primary key. |
| source_id | integer | Yes | Foreign key to sources. |
| quote | text | Yes | Evidence text. |
| location | text | No | Source-local line, section, or path hint. |
| content_hash | text | Yes | Unique quote digest. |
| confidence | real | Yes | Evidence confidence in the zero to one range. |
| created_at | real | Yes | Creation timestamp. |

#### `entity_classes`

Stores core classifier rows and discovered subtype names materialized from `CLS` entities. Entity classes follow a
spaCy-compatible classifier contract: `CLS` for class-definition entities, a base spaCy label such as `PERSON` or
`ORG`, or an object class such as `ORG.SoftwareProject`. The dynamic cache row stores the PascalCase subtype name,
such as SoftwareProject, so class meaning remains queryable through the `CLS` graph entity while validation and
LLM prompts can reuse a fast classifier catalog.
During a dream run, validated `CLS` entities are also held in a run-local catalog so later source frames can reuse
the class before a dry-run proposal is applied to this table.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| name | text | Yes | Primary key; core class key or PascalCase discovered subtype name. |
| description | text | No | Human-readable meaning. |
| status | text | Yes | Lifecycle state. |
| created_at | real | Yes | Creation timestamp. |

## Classifier Contract:

The knowledge graph does not use a closed domain ontology. It uses a stable named-entity classifier spine so
independent LLM calls can agree on broad object families, then lets subtypes emerge as graph objects. This makes a
class queryable, reviewable, and describable instead of leaving it as a hidden string attached to entities.

#### `CLS`

Purpose of the classifier: Represents a class-definition entity.

A class-definition entity is a normal graph entity whose job is to define a discovered class. Its entity class is
CLS, its canonical name is the PascalCase subtype name only, and its description explains what objects belong to
that class. These entities let query and review flows inspect class semantics directly. They also give the current
dream cycle and later dream cycles a stable vocabulary to reuse when processing isolated frames through the
run-local catalog and the persisted `entity_classes` cache.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| entity_class | text | Yes | Must be CLS. |
| canonical_name | text | Yes | Must be the PascalCase subtype name being defined. |
| description | text | Yes | Defines the semantic boundary of the class. |
| source_id | integer | Yes for applied deltas | Anchors where the class was discovered. |

#### `entity_class`

Purpose of the field: Stores the classifier key attached to every graph entity.

The field is not a free-form domain label. It must be either CLS, a base spaCy label, or a base label plus one
PascalCase subtype. During LLM extraction, the harness provides the known classifier catalog and validation
canonicalizes incoming values before a delta can become applicable. This prevents one source from producing
"tool", another "software artifact", and another "utility" when they describe the same structural kind.

| Accepted Shape | Meaning | Example Use |
|---|---|---|
| CLS | The entity defines a class. | A graph node that explains a discovered subtype. |
| spaCy base label | Broad named-entity family. | A person, organization, location, event, work, law, product, date, or quantity. |
| base plus subtype | Discovered specific classifier. | A reusable project, software artifact, vector store, or policy rule class. |

#### `SPACY_BASE.PascalCaseSubtype`

Purpose of the shape: Defines a discovered subtype under a stable spaCy base class.

The base part must be one of the supported spaCy entity labels. The subtype part must be a PascalCase programmatic
class name after normalization. A subtype should be introduced only when the text distinguishes a reusable class
that is more specific than the base label. The same delta should include a class-definition entity for the subtype
so the graph knows what that class means.

| Part | Constraint | Reason |
|---|---|---|
| BASE | spaCy-compatible entity label. | Keeps cross-document filtering stable. |
| subtype | PascalCase programmatic class name. | Keeps names comparable and usable in prompts. |
| class definition | Stored as a CLS entity. | Makes class semantics visible in graph queries. |

#### `MISC.Concept`

Purpose of the fallback: Captures a general concept only when no stronger classifier is justified.

This class is intentionally narrow. It is acceptable for abstract ideas that are not people, organizations,
products, events, places, works, laws, dates, or measurable values. It should not be used as the default answer for
every uncertain extraction. A high-quality NER pass should prefer a specific base label or discovered subtype when
the source text supports one.

#### `PERSON`

Purpose of the base label: Identifies people and person-like named actors.

Use this classifier for named humans or named role-bearing individuals when the source treats them as actors in
the graph. If a recurring subtype is meaningful, define it below this base with a class-definition entity rather
than inventing an unrelated class family.

#### `ORG`

Purpose of the base label: Identifies organizations, teams, projects, institutions, or structured groups.

Use this classifier when the object behaves like an organized entity with ownership, membership, governance, or
operational responsibility. Project-specific or institution-specific subtypes should stay under this base so query
can filter them together.

#### `ORG.SoftwareProject`

Purpose of the subtype: Identifies a software project as an organized graph object.

This subtype is useful when a repository, tool family, or software initiative is discussed as a coherent project
rather than as a single file or executable product. The class definition should explain the boundary that makes it
an organized project, such as shared purpose, components, maintainers, or roadmap.

#### `PRODUCT.SoftwareArtifact`

Purpose of the subtype: Identifies a concrete software artifact.

Use this subtype for scripts, packages, generated assets, command modules, vector stores, exported bundles, or
other product-like outputs that can be built, versioned, invoked, or inspected. If the artifact is instead a broad
project umbrella, an organization subtype may be a better classifier.

#### `PRODUCT.VectorStore`

Purpose of the subtype: Identifies an index or vector-backed retrieval artifact.

This subtype is useful when the source describes a persisted search index, embedding collection, or retrieval
database as a first-class object. It should be connected through relations such as indexes, retrieves, refreshes,
or supports, rather than stored as a copied sentence from the source.

#### `[CLS:"VectorStore"]`

Purpose of the rendered entity: Shows a class-definition entity in the common terminal syntax.

The renderer always uses the shared entity form with the class outside the quoted label. For a class definition,
the class is CLS and the quoted label is the PascalCase subtype being defined. This makes review output visually
explicit: the delta is proposing a class object, not a normal vector-store instance.

#### `entities`

Stores graph entities.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | integer | Yes | Primary key. |
| source_id | integer | No | Foreign key to sources; identifies the first source that produced the label. |
| entity_class | text | Yes | `CLS`, a spaCy base label, or a discovered subtype such as `ORG.SoftwareProject`. |
| canonical_name | text | Yes | Display label. |
| normalized_name | text | Yes | Case-folded matching label. |
| description | text | No | Short explanatory text. |
| confidence | real | Yes | Confidence in the zero to one range. |
| status | text | Yes | Active, contested, merged, pending, or rejected. |
| created_at | real | Yes | Creation timestamp. |
| updated_at | real | Yes | Last update timestamp. |
| merged_into_id | integer | No | Optional reference to canonical merged entity. |

#### `aliases`

Stores alternate labels for entities retained by older graph records and manual repository APIs. Current LLM dream
extraction does not propose aliases; entity canonical names are expected to be specific enough to stand on their
own.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | integer | Yes | Primary key. |
| entity_id | integer | Yes | Foreign key to entities. |
| alias | text | Yes | Alias label. |
| normalized_alias | text | Yes | Case-folded alias used for matching. |
| created_at | real | Yes | Creation timestamp. |

#### `relation_types`

Stores structural and discovered relation predicate keys.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| name | text | Yes | Primary key; normalized predicate key. |
| description | text | No | Human-readable meaning. |
| status | text | Yes | Lifecycle state. |
| created_at | real | Yes | Creation timestamp. |

#### `relations`

Stores source-anchored subject-predicate-object graph edges after the harness has resolved exact endpoint names.
Relation rows do not store literal object text or embedded evidence quotes; source metadata is carried by
`source_id`, and persisted endpoints are entity IDs.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | integer | Yes | Primary key. |
| source_id | integer | Yes | Foreign key to sources. |
| subject_entity_id | integer | Yes | Foreign key to subject entity. |
| predicate | text | Yes | Relation type key. |
| object_entity_id | integer | Yes | Foreign key to object entity. |
| confidence | real | Yes | Confidence in the zero to one range. |

#### `ontology_suggestions`

Stores proposed ontology evolution without changing database structure.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | integer | Yes | Primary key. |
| suggestion_type | text | Yes | Entity class or relation type suggestion. |
| name | text | Yes | Normalized suggested key. |
| description | text | No | Proposed meaning. |
| confidence | real | Yes | Suggestion confidence. |
| status | text | Yes | Pending, active, rejected, or related lifecycle state. |
| created_at | real | Yes | Creation timestamp. |

#### `pending_deltas`

Stores proposed graph deltas and validation reports.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | integer | Yes | Primary key. |
| source_id | integer | Yes | Foreign key to sources. |
| payload_json | text | Yes | Proposed delta JSON. |
| validation_json | text | Yes | Deterministic validation report JSON. |
| status | text | Yes | Pending by default. |
| created_at | real | Yes | Creation timestamp. |

#### `applied_deltas`

Stores applied graph delta audit records.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | integer | Yes | Primary key. |
| source_id | integer | Yes | Foreign key to sources. |
| payload_json | text | Yes | Applied accepted delta JSON. |
| created_at | real | Yes | Creation timestamp. |

#### `dream_runs`

Stores dream consolidation run summaries.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | integer | Yes | Primary key. |
| started_at | real | Yes | Run start timestamp. |
| finished_at | real | Yes | Run finish timestamp. |
| status | text | Yes | Completed or completed with warnings. |
| dry_run | integer | Yes | One when no accepted deltas were applied. |
| sources_seen | integer | Yes | Number of changed sources inspected. |
| deltas_proposed | integer | Yes | Number of generated deltas. |
| deltas_applied | integer | Yes | Number of applied accepted deltas. |
| errors_json | text | Yes | JSON array of non-blocking stage errors. |
| summary | text | No | Human-readable run summary. |

#### `entity_fts`

Stores graph-search rows for entities.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| entity_id | integer | Yes | Unindexed reference to entities. |
| canonical_name | text | Yes | Searchable entity label. |
| description | text | No | Searchable description. |
| entity_class | text | Yes | Searchable class key. |

#### `evidence_fts`

Stores graph-search rows for evidence.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| evidence_id | integer | Yes | Unindexed reference to evidence. |
| quote | text | Yes | Searchable quote. |
| location | text | No | Searchable source-local location. |

## Data Transfer Objects (DTOs):

## `brain.cli-dto`

### Data Transfer Objects (DTOs):

#### `ArgumentSchema`

Purpose of the DTO: Describes one positional argument or option in a command schema.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| flags | list of strings | Yes | Argument names or option aliases passed to argparse. |
| help | string | No | Help text. |
| action | optional string | No | Argparse action such as store_true. |
| type | optional string | No | Supported parser type marker such as int or float. |
| default | any | No | Default value. |
| required | boolean | No | Whether argparse should require the option. |
| nargs | optional string | No | Argparse nargs value. |

#### `SubcommandSchema`

Purpose of the DTO: Describes nested command metadata when a command supports subcommands.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| name | string | Yes | Subcommand name. |
| help | string | Yes | Help text. |
| arguments | list of ArgumentSchema | No | Nested command arguments. |

#### `CommandSchema`

Purpose of the DTO: Describes one top-level Brain CLI command.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| name | string | Yes | Top-level command name. |
| help | string | Yes | Short help text. |
| arguments | list of ArgumentSchema | No | Command arguments and options. |
| subcommands | list of SubcommandSchema | No | Nested command definitions. |
| subcommand_dest | optional string | No | Parser destination for nested commands. |
| domain | string | No | Command group for help and documentation. |

## `brain.query-dto`

### Data Transfer Objects (DTOs):

#### `GlobalQueryResultDTO`

Purpose of the DTO: Normalizes results from knowledge graph search, memory vector search, direct Markdown text
matching, and recoverable backend warnings under one reader-facing schema. Every usable result can carry source
structure, content, entities, and relations even when the backend originally returned a narrower payload.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| source | string | Yes | Backend family that produced the row. |
| mechanism | string | No | Retrieval mechanism such as graph, vector, or text. |
| kind | string | Yes | Backend-specific result kind. |
| rank | float | No | Numeric ordering hint where lower ranks sort earlier. |
| title | string | No | Human-readable title. |
| text | string | No | Compatibility excerpt mirrored from `content.excerpt`. |
| data | dictionary | No | Original backend payload for diagnostics and backward-compatible callers. |
| warning | string | No | Non-blocking warning text. |
| content | QueryContentDTO | No | Reader-facing content block shown by default in CLI output. |
| source_ref | QuerySourceRefDTO | No | Structured source reference with logical domain, reader command, path, scope, type, and hierarchy. |
| entities | list of QueryEntityDTO | No | Entity context involved in the result. |
| relations | list of QueryRelationDTO | No | Relation context involved in the result. |

#### `QueryContentDTO`

Purpose of the DTO: Carries the descriptive content that should be visible to readers by default.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| title | string | No | Result title. |
| excerpt | string | No | Bounded excerpt printed by terminal output and exposed to JSON callers. |
| body | string | No | Longer content body when available and safe to expose. |
| location | string | No | Source-local line, section, or evidence location hint. |

#### `content.excerpt`

Purpose of the field: Provides the default reader-facing text exposed by query result renderers.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| content.excerpt | string | No | Bounded content excerpt. CLI output prints this field by default; JSON callers can use it as the primary display body. |

#### `QuerySourceRefDTO`

Purpose of the DTO: Describes where a result came from in a navigable source hierarchy.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| scope | string | No | Runtime or knowledge scope such as global or local. |
| source_type | string | No | Source family such as memory, diary, profiles, or workspace_logs. |
| domain | string | No | Logical source domain derived from the stable source path. |
| read_command | string | No | CLI command that reads the source without exposing the physical file path as the primary UI. |
| path | string | No | Stable source path. |
| title | string | No | Human-readable source title. |
| structure | list of string | No | Path segments rendered as source hierarchy. |
| line_number | optional integer | No | Source-local line number for direct text hits. |

#### `source_ref`

Purpose of the field: Provides the normalized source structure attached to each query result.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| source_ref | QuerySourceRefDTO | No | Logical domain, source reader command, stable source path, source type, scope, title, hierarchy segments, and optional line number. |

#### `QueryEntityDTO`

Purpose of the DTO: Carries entity context in query results.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | optional integer | No | Entity database identifier when the result came from KG. |
| entity_class | string | No | Entity type/class. |
| name | string | No | Canonical entity name. |
| description | string | No | Entity description. |
| confidence | float | No | Confidence score in the zero-to-one range. |

#### `QueryRelationDTO`

Purpose of the DTO: Carries relation context in query results.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | optional integer | No | Relation database identifier when the result came from KG. |
| predicate | string | No | Relation predicate. |
| subject | QueryEntityDTO | No | Subject endpoint. |
| object | QueryEntityDTO | No | Object endpoint. |
| confidence | float | No | Confidence score in the zero-to-one range. |
| source_path | string | No | Stable source path supporting the relation. |

## `brain.application.knowledge-dto`

### Data Transfer Objects (DTOs):

#### `StageModelConfigDTO`

Purpose of the DTO: Configures one model-backed knowledge processing stage.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| model | string | No | Provider model identifier. |
| base_url | string | No | OpenAI-compatible API base URL. |
| api_key | string | No | Environment reference or resolved API token. |
| temperature | float | No | Range zero to two. |
| max_tokens | integer | No | Range 128 to 20000. Default is 6000 so structural extraction can return dense entity and relation sets. |
| enabled | boolean | No | Whether the stage may call the external model. |

#### `KnowledgeConfigDTO`

Purpose of the DTO: Validates private knowledge graph runtime configuration.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| version | integer | No | Config schema version. |
| minimum_confidence | float | No | Range zero to one. |
| stages | dictionary of StageModelConfigDTO | No | Per-stage model configuration. |

#### `MemoryConfigDTO`

Purpose of the DTO: Validates the memory/vector portion of `brain_configs.json`.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| embedding_model | StageModelConfigDTO | No | Embedding model configuration used by vectorstore helpers. |
| text_model | StageModelConfigDTO | No | Text model configuration retained for memory-facing helpers. |

#### `BrainConfigsDTO`

Purpose of the DTO: Validates the unified global runtime config at `core/configs/brain_configs.json`.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| version | integer | No | Config schema version. |
| agent_dir | string | Yes | Canonical absolute root for agent-owned memory, snippets, and authored state. |
| knowledge | KnowledgeConfigDTO | No | Knowledge graph and LLM-stage configuration. |
| memory | MemoryConfigDTO | No | Memory/vector configuration. |

#### `SourceDTO`

Purpose of the DTO: Transfers stable source identity from discovery into repository ingestion for one graph scope.
It deliberately does not carry hashes, mtimes, or processed timestamps. Those values belong to `brain_sources.db`,
not to graph objects.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | optional integer | No | Database identifier after persistence. |
| source_type | string | Yes | Source family such as memory, diary, profiles, or workspace_logs. |
| path | string | Yes | Stable source path. |
| title | string | No | Human-readable source title. |
| active | boolean | No | Whether the source is present. |

#### `SourceRegistryRecordDTO`

Purpose of the DTO: Represents one file row from a scoped source registry. It is used by the fast diff checker
before query or dream work decides whether heavier consumers need to run.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | optional integer | No | Source registry row identifier. |
| path | string | Yes | Stable source path such as memory/profiles/developer/1 - instructions.md or $agent/logs/2026-07/03-07-2026.log.md. |
| mtime | float | No | Filesystem modification timestamp from the source registry. |
| size | string | No | Human-readable file size. |
| lines | string | No | Human-readable line count. |
| entries | integer | No | Lightweight source entry count. |
| source_type | string | No | Source family. |
| title | string | No | Human-readable source title. |
| active | boolean | No | Whether the source currently exists. |

#### `SourceRegistryCheckDTO`

Purpose of the DTO: Reports the result of refreshing a source registry or comparing it against one consumer's
processed state.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| registry_path | string | No | SQLite source registry path checked. |
| scanned | integer | No | Number of source records discovered during refresh. |
| changed | list of SourceRegistryRecordDTO | No | Records whose current mtime differs from the consumer state. |
| deleted | list of strings | No | Source paths previously processed by the consumer but now inactive in the registry. |

#### `EvidenceDTO`

Purpose of the DTO: Transfers evidence quotes into the repository.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | optional integer | No | Database identifier after persistence. |
| source_id | integer | Yes | Parent source identifier. |
| quote | string | Yes | Supporting quote. |
| location | string | No | Source-local hint. |
| content_hash | string | No | Quote digest, generated when omitted. |
| confidence | float | No | Range zero to one. |

#### `KnowledgeFrameDTO`

Purpose of the DTO: Carries semantic model input prepared by the harness before LLM extraction. It is not stored as
graph state and must not expose filesystem provenance to the model prompt.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| frame_kind | string | No | Semantic frame family, such as change_log_records, diary_records, or knowledge_records. |
| title | string | No | Human-readable title derived from content, not from the source path. |
| body | string | No | Model-ready text with source paths and source IDs removed. |
| source_type | string | No | Internal harness source family used for frame selection, including workspace_logs for local logs. |
| original_chars | integer | No | Raw source character count for diagnostics. |

#### `EntityDTO`

Purpose of the DTO: Represents a source-anchored semantic label. The label is the object in the graph; the source
row records where that label was discovered. The string renderer emits the compact form `[class:"name"]`. When the
entity defines a discovered class, `entity_class` is `CLS`, `canonical_name` is the PascalCase subtype name, and
`description` explains the class semantics.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | optional integer | No | Database identifier after persistence or local candidate ID inside a pending delta. |
| source_id | optional integer | No | Source row identifier; validation requires it before applying a delta. |
| entity_class | string | No | `CLS`, spaCy base label, or `SPACY_BASE.PascalCaseSubtype`; defaults to `MISC.Concept`. |
| canonical_name | string | Yes | Display label; for `CLS` entities this is the PascalCase subtype name being defined. |
| description | string | No | Short description derived from source content without becoming a relation object. |
| confidence | float | No | Range zero to one. |

#### `AliasDTO`

Purpose of the DTO: Represents an alternate surface form for an entity in legacy or manual repository workflows.
The current LLM dream contract strips aliases before validation.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | optional integer | No | Database identifier after persistence. |
| entity_ref | integer or string | Yes | Entity ID or entity label reference. |
| alias | string | Yes | Alias label. |

#### `RelationDTO`

Purpose of the DTO: Represents a source-anchored relation between two entity IDs after exact endpoint-name
resolution. It never stores literal object text, source paths, or embedded evidence quotes. Terminal review renders
endpoints as `[class:"name"]` whenever the pending delta or repository entity catalog can resolve them.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | optional integer | No | Database identifier after persistence. |
| source_id | optional integer | No | Source row identifier; validation requires it before applying a delta. |
| subject_id | optional integer | No | Subject entity ID, or a local candidate ID that maps to an entity in the same delta. |
| object_id | optional integer | No | Object entity ID, or a local candidate ID that maps to an entity in the same delta. |
| predicate | string | No | Normalized discovered relation key. |
| confidence | float | No | Range zero to one. |

#### `LLM relation proposal`

Purpose of the raw model payload: Lets the model construct relations using exact canonical entity names rather
than numeric IDs. This shape is sanitized into `RelationDTO` before validation. Candidate IDs are assigned by the
local harness after entity detection and are never shown to the relation extraction prompt.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| subject_name | string | Yes | Must exactly match a current delta entity `canonical_name` or persisted graph entity name. |
| object_name | string | Yes | Must exactly match a current delta entity `canonical_name` or persisted graph entity name. |
| predicate | string | Yes | Lower snake_case verbal nucleus; must not contain endpoint names. |
| confidence | float | No | Range zero to one. |

The LLM relation proposal must not include `subject_id`, `object_id`, endpoint indexes, source IDs, file paths,
evidence quotes, or newly invented endpoint names. If a name cannot be resolved exactly, validation rejects that
relation while keeping the rest of the delta reviewable.

#### `LLM entity proposal`

Purpose of the raw model payload: Lets NER detect object labels using a stable classifier contract.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| entity_class | string | Yes | Must be `CLS`, a spaCy base label, or `SPACY_BASE.PascalCaseSubtype`. |
| canonical_name | string | Yes | Compact entity label, or PascalCase subtype name when `entity_class` is `CLS`. |
| description | string | No | Short meaning of the object or class. |
| confidence | float | No | Range zero to one. |

When a NER stage discovers a subtype such as `PRODUCT.VectorStore`, the same delta must include a class entity
`[CLS:"VectorStore"]` with a useful description unless that subtype already exists in the `entity_classes` cache.
The local sanitizer does not create missing `CLS` entities; deterministic validation rejects dynamic subtype
entities that lack a registered or same-delta class definition.

#### `canonical_name`

Purpose of the DTO field: Names the entity exactly as the graph should display and match it. LLM relation
proposals must use this value verbatim when naming endpoints.
The value must be a compact object label, not copied prose. File-like and module-like labels such as README.md or
generate_wiki.js are valid when they identify a real artifact rather than a sentence.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| canonical_name | string | Yes | Compact entity label; must not be a full sentence or copied instruction. Technical artifact labels with extensions are valid. |

#### `subject_name`

Purpose of the raw model field: Names the relation subject by exact entity canonical name before the harness
resolves it into an internal endpoint ID.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| subject_name | string | Yes | Must match a current delta entity name or persisted graph entity name. |

#### `object_name`

Purpose of the raw model field: Names the relation object by exact entity canonical name before the harness
resolves it into an internal endpoint ID.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| object_name | string | Yes | Must match a current delta entity name or persisted graph entity name. |

#### `source_id`

Purpose of the DTO field: Anchors an entity or relation to the row in `sources` that discovered it.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| source_id | optional integer | Yes for applicable deltas | The repository tolerates legacy nulls, but validation requires a source before application. |

#### `subject_id`

Purpose of the DTO field: Identifies the subject endpoint for a relation.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| subject_id | optional integer | Yes for applicable relations | May be a persisted entity ID or a positive local candidate ID inside the same delta. |

#### `object_id`

Purpose of the DTO field: Identifies the object endpoint for a relation.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| object_id | optional integer | Yes for applicable relations | May be a persisted entity ID or a positive local candidate ID inside the same delta. |

#### `__str__`

Purpose of the DTO method: Provides a stable compact render form for terminal review and debugging.

| Owner | Format | Description |
|---|---|---|
| EntityDTO | `[class:"name"]` | Shows the semantic class and canonical label. |
| RelationDTO | `[class:"subject"] - ("predicate" at confidence) -> [class:"object"]` | Shows endpoint labels when available, predicate, and confidence. |

#### `[class:"subject"] - ("predicate" at confidence) -> [class:"object"]`

Purpose of the render contract: Displays one relation without leaking source text into the edge. The subject and
object endpoints render through the entity display contract when the review command can resolve them from the
pending delta or repository entity catalog. The `predicate` value is the normalized verbal relation key, and
`confidence` is the score used by validation and review output.

#### `SchemaSuggestionDTO`

Purpose of the DTO: Represents an ontology evolution proposal without changing database structure.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| suggestion_type | string | Yes | Entity class or relation type. |
| name | string | Yes | Suggested ontology key. |
| description | string | No | Suggested meaning. |
| confidence | float | No | Range zero to one. |

#### `KnowledgeDeltaDTO`

Purpose of the DTO: Bundles proposed graph changes for one source.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| source_path | string | No | Source path that produced the delta. |
| entities | list of EntityDTO | No | Entity candidates. |
| aliases | list of AliasDTO | No | Legacy/manual aliases. LLM dream extraction emits none and validation strips them. |
| relations | list of RelationDTO | No | Relation candidates. |
| schema_suggestions | list of SchemaSuggestionDTO | No | Ontology evolution proposals. |
| rationale | string | No | Explanation of the proposal. |

#### `ValidationReportDTO`

Purpose of the DTO: Reports deterministic validation results for a proposed delta.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| valid | boolean | No | True when accepted records remain after validation. |
| errors | list of strings | No | Blocking failures. |
| warnings | list of strings | No | Non-blocking filtered-record reasons. |
| accepted_delta | KnowledgeDeltaDTO | No | Filtered delta containing applicable records. |

#### `ConsolidationDecisionDTO`

Purpose of the DTO: Records one dream or consolidation decision.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| action | string | Yes | Action such as propose, apply, skip, promote, or contest. |
| reason | string | No | Human-readable reason. |
| entity_id | optional integer | No | Related entity identifier. |
| relation_id | optional integer | No | Related relation identifier. |

#### `DreamRunDTO`

Purpose of the DTO: Summarizes one cognitive consolidation run.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| id | optional integer | No | Database identifier after persistence. |
| status | string | No | Run status. |
| dry_run | boolean | No | Whether accepted changes were only proposed. |
| sources_seen | integer | No | Number of changed sources inspected. |
| deltas_proposed | integer | No | Number of proposed deltas. |
| deltas_applied | integer | No | Number of applied deltas. |
| pending_delta_ids | list of integers | No | Persisted proposal identifiers written for review. |
| errors | list of strings | No | Non-blocking run errors. |
| decisions | list of ConsolidationDecisionDTO | No | Run decisions. |
| summary | string | No | Human-readable summary. |

#### `JsonDict`

Purpose of the DTO: Type alias for JSON-compatible dictionaries used by knowledge helpers.

| Field Name | Data Type | Required (Yes/No) | Constraints / Description |
|---|---|---|---|
| value | dictionary | Yes | Keys are strings and values are JSON-compatible. |
