# Brain Interfaces & Contracts

## Index:
- [Interface Index](#interface-index)
- [Functional Interfaces](#functional-interfaces)
- [Service Contracts](#service-contracts)
- [Repository Contracts](#repository-contracts)

## Interface Index:

```python
def main(argv: list[str] | None = None) -> int: ...
def run_cli(argv: list[str] | None = None) -> int: ...
def build_argument_parser(command_modules: list[ModuleType]) -> argparse.ArgumentParser: ...
def dispatch_command(args: argparse.Namespace) -> int: ...
def get_action_handler(command_name: str) -> Callable | None: ...
def query_global(text: str, domain: str = "all", limit: int = 5, scope: str = "all", source: str | None = None, mechanism: str = "all", knowledge_scope: str = "all") -> list[GlobalQueryResultDTO]: ...
def validate_delta(delta_dto: KnowledgeDeltaDTO, source_content: str, minimum_confidence: float = 0.65, repository: KnowledgeRepository | None = None, known_class_names: set[str] | None = None) -> ValidationReportDTO: ...
def export_jsonld(repository: KnowledgeRepository) -> dict[str, Any]: ...
def render_stage_prompt(stage_name: str, values: dict[str, str]) -> str: ...
def get_stage_system_prompt(stage_name: str) -> str: ...
def ensure_brain_source_indexes(agent_home: Path | None = None, workspace_root: Path | None = None) -> list[SourceRegistryCheckDTO]: ...
def refresh_source_registry(scope: str, root: Path, root_prefix: str, suffixes: tuple[str, ...], source_type_resolver: SourceTypeResolver, agent_home: Path | None = None, workspace_root: Path | None = None) -> SourceRegistryCheckDTO: ...
def diff_sources_for_consumer(scope: str, consumer_name: str, root: Path, root_prefix: str, suffixes: tuple[str, ...], source_type_resolver: SourceTypeResolver, force_all: bool = False, agent_home: Path | None = None, workspace_root: Path | None = None) -> SourceRegistryCheckDTO: ...
def list_source_registry_records(scope: str, root_prefix: str, active_only: bool = True, agent_home: Path | None = None, workspace_root: Path | None = None) -> list[SourceRegistryRecordDTO]: ...
def mark_consumer_source_processed(scope: str, consumer_name: str, source_path: str, mtime: float, agent_home: Path | None = None, workspace_root: Path | None = None) -> None: ...
def migrate_brain_runtime_stores(agent_home: Path | None = None, workspace_root: Path | None = None) -> RuntimeMigrationReportDTO: ...
LLMEventCallback = Callable[[dict[str, Any]], None]
ApplicationEventCallback = Callable[[dict[str, Any]], None]
```

```python
class KnowledgeRepository:
    def status(self) -> dict[str, Any]: ...
    def upsert_source(self, source_dto: SourceDTO) -> int: ...
    def add_evidence(self, evidence_dto: EvidenceDTO) -> int: ...
    def upsert_entity(self, entity_dto: EntityDTO) -> int: ...
    def upsert_relation(self, relation_dto: RelationDTO) -> int: ...
    def list_pending_deltas(self, limit: int = 10, status: str = "pending") -> list[dict[str, Any]]: ...
    def get_pending_delta(self, delta_id: int) -> dict[str, Any] | None: ...
    def update_pending_delta_status(self, delta_id: int, status: str) -> None: ...
    def delete_pending_deltas(self, delta_ids: list[int]) -> int: ...
```

## Functional Interfaces:

### `core/brain/src/brain/cli.py`

**What It Does:** Defines the thin process entry point for the Brain CLI.

**Used By:** Workspace brain wrappers and direct module invocation.

**Contract:** Accepts optional argv input, configures Windows console behavior when available, delegates to
`run_cli()`, and returns zero or nonzero process status.

#### `main()`

**What It Does:** Runs the CLI entrypoint for one invocation.

**Used By:** Module execution and workspace wrappers.

**Contract:** Does not build parsers, resolve commands, or execute handlers directly.

### `core/brain/src/brain/presentation/router/services/cli_runtime_service.py`

**What It Does:** Coordinates global flag extraction, parser construction, command dispatch, and store-error
rendering for one CLI invocation.

**Used By:** `brain.cli.main()`.

**Contract:** Accepts argv values, strips router-level `--color` and `--verbose-log` before command-specific
parsing, injects those values into the parsed namespace, and returns an integer process code.

#### `run_cli()`

**What It Does:** Runs the parser and router services for one CLI invocation.

**Used By:** CLI entrypoint and tests.

**Contract:** It does not own command metadata or command action logic.

### `core/brain/src/brain/presentation/parser/services/argument_parser_service.py`

**What It Does:** Builds an `argparse` parser from declarative command schemas.

**Used By:** CLI runtime service.

**Contract:** Reads command schemas but does not execute actions or import application services.

#### `build_argument_parser()`

**What It Does:** Creates a parser with one subparser per registered command schema.

**Used By:** CLI runtime service and tests.

**Contract:** Returns an argparse parser from explicit command modules.

### `core/brain/src/brain/presentation/router/services/command_router_service.py`

**What It Does:** Resolves a parsed command name into an executable action.

**Used By:** CLI runtime service.

**Contract:** Defaults empty commands to `help`; unknown commands raise `BrainStoreError`.

#### `dispatch_command()`

**What It Does:** Executes the action handler matching parsed arguments.

**Used By:** CLI runtime service.

**Contract:** The router obtains handlers from `brain.presentation.actions.registry`, not from command metadata modules.

### `core/brain/src/brain/presentation/commands/registry.py`

**What It Does:** Registers declarative command metadata modules.

**Used By:** Parser, help rendering, and action registry binding.

**Contract:** Modules in `brain.presentation.commands` expose `SCHEMA` only and do not expose `handle()`.

### `core/brain/src/brain/presentation/actions/registry.py`

**What It Does:** Registers executable CLI action handlers.

**Used By:** Command router.

**Contract:** Maintains a handler for every command schema name.

#### `get_action_handler()`

**What It Does:** Returns the executable handler for a command name.

**Used By:** Command router.

**Contract:** Returns `None` when a command name is not registered.

### `core/brain/src/brain/application/querying/service.py`

**What It Does:** Orchestrates global retrieval across knowledge graph index search, memory vector search, and direct
Markdown text matching. Implementation is split across `brain.application.querying.service`, `brain.application.querying.backends`,
`brain.application.querying.planning`, `brain.application.querying.ranking`, and `brain.application.querying.synthesis`. Before querying, it performs a
lightweight source-index fast-pass so stale global memory or local log catalogs are detected by mtime.

**Used By:** The global query command and tests.

**Contract:** Returns normalized result DTOs with a shared `content`, `source_ref`, `entities`, and `relations`
shape. Backend failures become warning rows when another selected backend can still answer. Reader commands are
carried in `source_ref.read_command`; human rendering uses them in source headers instead of exposing source paths
as the primary navigation affordance. Knowledge graph queries also emit warning rows when the selected graph scope
has source mtimes newer than the knowledge_graph consumer state and should be refreshed through `dream`.

#### `query_global()`

**What It Does:** Searches selected brain backends through one service contract.

**Used By:** The global query command.

**Contract:** Inputs are query text, optional memory domain, result limit, source selector, mechanism selector, and
knowledge scope selector. The output is a sorted list of normalized query result DTOs. Usable results expose
reader-facing content by default, source hierarchy, reader command, entity context, and relation context. Unsupported
source, mechanism, or knowledge scope values raise a value error before backend calls.

### `core/brain/src/brain/application/querying/dtos.py`

**What It Does:** Defines the shared DTO schema returned by every global query backend.

**Used By:** Query service, query command rendering, JSON callers, and tests.

**Contract:** `GlobalQueryResultDTO` is the outer result shape. Its `content`, `source_ref`, `entities`, and
`relations` fields are the stable reader-facing schema; `data` remains diagnostic backend payload.

### `core/brain/src/brain/application/querying/*_mapping.py`

**What It Does:** Converts backend-specific KG, vector, and direct text matches into the shared query DTO shape.
Source references, text excerpts, vector results, and knowledge graph rows are split across
`brain.application.querying.source_refs`, `text_mapping`, `vector_mapping`, and `knowledge_mapping`.

**Used By:** Query service.

**Contract:** Mapping functions may read bounded source excerpts to make KG hits descriptive, but they do not mutate
knowledge stores. They preserve stable source paths for diagnostics while also deriving reader commands such as
`read-diary -d <date> --time <HH:MM>`, `read-log -d <date> --time <HH:MM>`, `read-profile <name>`, or
`get-memory-entry "<domain.key>"`. Direct text matches inside diary entries infer the surrounding entry title and
minute from the nearest dated heading so the result can navigate to the same source granularity as vector matches.

### `core/brain/src/brain/infrastructure/sources/diff_checker.py`

**What It Does:** Owns the shared fast mtime diff layer for brain knowledge sources.

**Used By:** Global query, knowledge source discovery, log indexing, dream source selection, and any future brain
knowledge consumer that needs to know whether its input corpus changed before doing heavier work.

**Contract:** Source indexes describe the current filesystem state in JSON. Consumer state JSON records what one
consumer has already processed. The checker compares these two JSON surfaces and never writes graph rows or
vectorstore chunks.

#### `ensure_brain_source_indexes()`

**What It Does:** Refreshes the global and local SQLite source registries from filesystem mtimes.

**Used By:** The global query fast-pass and any command that wants all lightweight brain source catalogs current.

**Contract:** Returns a list of `SourceRegistryCheckDTO` values. It updates `core/database/sources/brain_sources.db`
for shared memory sources and `$agent/database/brain_sources.db` for workspace logs. It does not update ChromaDB,
pending deltas, or graph objects.

#### `refresh_source_registry()`

**What It Does:** Scans one source tree and stores current source metadata in the scoped source registry.

**Used By:** Memory registry refreshes, log registry refreshes, query freshness checks, and dream source
selection.

**Contract:** Writes or updates rows in the registry `sources` table with stable path, source type, title, mtime,
size label, line-count label, entry count, active state, and registry update timestamp. Missing rows under the
same root prefix are marked inactive instead of being removed.

#### `diff_sources_for_consumer()`

**What It Does:** Compares active source mtimes with one consumer's processed mtimes.

**Used By:** Knowledge source ingestion and query staleness checks.

**Contract:** Refreshes the scoped registry first, then returns changed records when `sources.mtime` differs from
`source_consumers.processed_mtime` for the requested consumer. Deleted paths are inactive source rows that still
have consumer state. The `force_all` option returns every active source as changed without marking it processed.

#### `list_source_registry_records()`

**What It Does:** Reads registered source rows for one scope and root prefix.

**Used By:** Memory structure commands and lightweight diagnostics.

**Contract:** Returns `SourceRegistryRecordDTO` rows ordered by path. Active-only mode hides rows for files that
were previously registered but no longer exist.

#### `mark_consumer_source_processed()`

**What It Does:** Records that one consumer has processed one source mtime.

**Used By:** Dream after the configured model stages produce a proposal or an intentional empty result for a
source.

**Contract:** Writes or updates one `source_consumers` row in the scoped source registry. If the source identity
row is missing, it creates a minimal `sources` row so the processed mtime still has a durable anchor.

#### `knowledge_graph`

**What It Does:** Names the source-state consumer used by the knowledge graph.

**Used By:** `diff_sources_for_consumer()`, `mark_consumer_source_processed()`, dream source selection, and query
staleness warnings.

**Contract:** The consumer namespace isolates KG processed mtimes from other brain consumers. It is stored in
`source_consumers.consumer`; it is not a model prompt token.

#### `force_all`

**What It Does:** Forces a consumer diff to treat every indexed source as changed.

**Used By:** Dream prune cycles that rebuild a graph and must repopulate it from the full current source index.

**Contract:** The option affects the returned diff only. It refreshes the source registry like any diff call, but
does not alter consumer processed state or bypass deterministic validation.

#### `processed_at`

**What It Does:** Records when a consumer finished processing a source mtime.

**Used By:** `source_consumers` rows written after a dream source pass completes.

**Contract:** The value is an audit timestamp in SQLite. Freshness comparisons use `processed_mtime`, not
`processed_at`.

### `core/brain/src/brain/application/memory/service.py`

**What It Does:** Owns Markdown memory writes, reads, deletions, and domain orchestration. Path validation and
atomic filesystem primitives live in `brain.application.memory.paths`; embedded Markdown section edits live in
`brain.application.memory.markdown_sections`; structural diagnostics live in `brain.application.memory.diagnostics`.

**Used By:** Memory command modules and index maintenance.

**Contract:** Uses validated domain and key names to resolve paths under the memory root. Raises store errors for
invalid names, missing entries, unsafe deletes, or malformed embedded Markdown sections.

#### `write_instance()`

**What It Does:** Writes content to one memory entry.

**Used By:** Memory write commands.

**Contract:** Accepts category, key, and content. Writes atomically and returns the written path.

#### `read_instance()`

**What It Does:** Reads one memory entry.

**Used By:** Memory read commands.

**Contract:** Accepts category and key, returns text content, and raises when the entry is unavailable.

#### `delete_instance()`

**What It Does:** Deletes one memory entry.

**Used By:** Memory delete commands.

**Contract:** Accepts category and key. It removes only the resolved entry path.

#### `doctor_report()`

**What It Does:** Builds a structural health report for the memory tree.

**Used By:** Workspace checks and initialization.

**Contract:** Returns a JSON-compatible diagnostic payload.

### `core/brain/src/brain/application/memory/indexing/index_service.py`

**What It Does:** Builds and updates the memory source registry from Markdown memory files. Registry refresh, tree
construction, stats, and vector synchronization live under `brain.application.memory.indexing` and `brain.application.memory.vector_sync`.

**Used By:** Memory writes, deletes, initialization, and manual index commands.

**Contract:** Reads memory files, extracts metadata and content statistics, writes the index, and can heal stale
index state.

#### `build_full_index()`

**What It Does:** Scans the complete memory tree and builds a fresh index payload.

**Used By:** Initialization and full index rebuild commands.

**Contract:** Returns a JSON-compatible index dictionary and does not require the vectorstore.

#### `update_index_record()`

**What It Does:** Updates one memory index record after an entry changes.

**Used By:** Memory write and delete commands.

**Contract:** Accepts category, key, and deleted state. It updates the persisted index for that record.

### `core/brain/src/brain/application/logs/index_service.py`

**What It Does:** Rebuilds the workspace log index. Parsing, vector synchronization, index rendering,
source-registry refresh, and legacy migration live under `brain.application.logs`.

**Used By:** Log append, edit, read, update, and initialization commands.

**Contract:** Reads dated log files, extracts entries, groups them by domain, writes the human-readable log index,
and refreshes `$agent/database/brain_sources.db` so local knowledge consumers can detect log changes by mtime.

#### `rebuild_logs_index()`

**What It Does:** Rebuilds the workspace log index.

**Used By:** Log commands and initialization.

**Contract:** Accepts the workspace root and returns the written index path.

#### `migrate_legacy_md_logs()`

**What It Does:** Converts legacy Markdown log files into the current log format.

**Used By:** Log index update repair mode.

**Contract:** Accepts the workspace root and returns migrated path summaries.

### `core/brain/src/brain/infrastructure/vectorstores/manager.py`

**What It Does:** Manages embedding-backed ChromaDB collections for memory and local log retrieval. Vectorstore
configuration loading lives in `brain.infrastructure.vectorstores.settings`; embedding failure recovery helpers live in
`brain.infrastructure.vectorstores.recovery`; embedding API access, chunking, ChromaDB collection access, and log-specific vector
behavior live under `brain.infrastructure.vectorstores`.

**Used By:** Vectorstore commands, global query vector mode, and log query commands.

**Contract:** Provides update, rebuild, search, and status operations. Embedding provider failures are reported
through explicit unavailable-error helpers so callers can decide whether to continue. Diary and log sources are
split at entry granularity: the vector text is the body content, while title, date, normalized HH:MM, stable source
path, and reader command remain metadata for query rendering and CLI navigation.

#### `VectorStoreManager`

**What It Does:** Encapsulates collection access, embedding calls, document chunking, update, rebuild, search, and
status behavior.

**Used By:** Vectorstore commands and query services.

**Contract:** Instances are configured with a database path and collection name. Search returns dictionaries with
text, metadata, similarity, and ranking values. For diary and log chunks, callers should treat `metadata.body` as
the display body and `metadata.read_command` as the source access command.

### `core/brain/src/brain/infrastructure/runtime/migration_service.py`

**What It Does:** Migrates legacy workspace-local runtime stores into the current `$agent/database` layout.
DTOs, idempotent migration steps, source-state import, and orchestration live under `brain.infrastructure.runtime`.

**Used By:** `brain init` before memory, log, vectorstore, or knowledge graph preparation runs.

**Contract:** Moves old local knowledge databases from
`$agent/data/knowledge/knowledge.db` or `$agent/data/knowledge/angi_kg.sqlite3` to
`$agent/database/sources.db` when the target is absent. Moves old vectorstores
from `$agent/data/vectorstore` to `$agent/database/brain_vectorstore` when the
target is absent or empty.
Imports legacy `source_state.json` consumer mtimes into `brain_sources.db`, removes retired derived source index
JSON files, and removes empty legacy runtime directories. If both old and new locations contain substantive data,
it leaves the old store in place and reports a warning instead of overwriting either store.

#### `migrate_brain_runtime_stores()`

**What It Does:** Executes all idempotent runtime store migrations for one shared home and one workspace.

**Used By:** Session initialization.

**Contract:** Returns a `RuntimeMigrationReportDTO` with performed actions and warnings. It accepts optional
`agent_home` and `workspace_root` overrides for tests and future repo tooling. It performs no schema mutation
inside knowledge databases; schema initialization remains owned by the knowledge repository.

#### `RuntimeMigrationReportDTO`

**What It Does:** Reports completed runtime migration actions and non-fatal warnings.

**Used By:** `brain init` terminal output and migration tests.

**Contract:** `actions` contains structured source-target operations. `warnings` contains skipped migrations,
usually because both the old and new locations already contain substantive data.

#### `agent_home`

**What It Does:** Overrides the shared HOME directory used by runtime migration.

**Used By:** Tests, future maintenance commands, and any caller migrating a non-default shared home.

**Contract:** Used for source-state import context and test isolation. Core-owned
global stores remain fixed under the Brain package's containing `core`
directory; workspace-local paths come from `workspace_root`.

#### `workspace_root`

**What It Does:** Overrides the local workspace root used by runtime migration.

**Used By:** Tests, `create-brain`-style tooling, and future batch migration helpers.

**Contract:** When omitted, the migrator resolves the active working directory or `WORKSPACE_ROOT`. The local
runtime target remains `$agent/database` under this root.

## Service Contracts:

### `core/brain/src/brain/config.py`

**What It Does:** Defines constants shared across the brain package.

**Used By:** Runtime path resolvers, knowledge configuration loading, vectorstore settings, and validation helpers.

**Contract:** Contains names, default strings, scope tuples, stage-name tuples, and static marker lists only. It
does not read environment variables, create directories, read or write JSON, open databases, or perform validation.

### `core/brain/src/brain/infrastructure/runtime/paths.py`

**What It Does:** Resolves and prepares runtime filesystem locations.

**Used By:** Runtime migration, source registries, vectorstores, and knowledge configuration storage.

**Contract:** Discovers the containing `core` directory from the installed Brain
package, reads canonical `agent_dir` for agent-owned memory and snippets,
resolves `WORKSPACE_ROOT` for local data, and applies private-directory
`.gitignore` contracts when directories are created.

### `core/brain/src/brain/application/knowledge/runtime/scopes.py`

**What It Does:** Normalizes knowledge graph scope selectors and expands selected runtime roots.

**Used By:** Knowledge commands, repositories, dream, and query.

**Contract:** Accepts `global`, `local`, or `all` where appropriate. It returns ordered scope/path pairs without
merging graph databases or making scoped IDs interchangeable.

### `core/brain/src/brain/application/knowledge/runtime/config_store.py`

**What It Does:** Loads, creates, validates, and repairs the unified knowledge runtime configuration file.

**Used By:** Knowledge initialization, repository construction, dream runs, and LLM calls.

**Contract:** Creates the core config file when missing, validates unified Brain
config JSON into DTOs, removes retired path fields, and backfills missing model
stages. Fixed database paths are not configuration. The local graph runtime does
not own a separate config file.

#### `get_knowledge_root()`

**What It Does:** Resolves a physical database runtime root.

**Used By:** Repository construction, initialization, and scoped command actions.

**Contract:** Accepts `global` or `local`. Global resolves to `core/database/knowledge`; local resolves to
`$agent/database`.

#### `get_shared_config_path()`

**What It Does:** Resolves the one config file used by all knowledge scopes.

**Used By:** Knowledge initialization, status reporting, repository construction, and LLM client configuration.

**Contract:** Always returns the global `core/configs/brain_configs.json` path.

#### `iter_knowledge_roots()`

**What It Does:** Expands a scope selector into concrete runtime roots.

**Used By:** Query, status, init, dream, and export commands.

**Contract:** Accepts `global`, `local`, or `all`. It returns ordered scope/path pairs without merging the
underlying databases.

#### `ensure_knowledge_config()`

**What It Does:** Creates and validates runtime knowledge configuration.

**Used By:** Knowledge initialization, repository construction, and model stage configuration.

**Contract:** Returns a validated config DTO. Missing files are created with default per-stage model settings in
the global knowledge config root.

#### `load_knowledge_config()`

**What It Does:** Loads runtime knowledge configuration from disk.

**Used By:** Dream runner, LLM client, and repository helpers.

**Contract:** Returns a validated DTO and repairs missing stage keys by writing the expanded config back to disk.

### `core/brain/src/brain/application/knowledge/pipeline/schema.py`

**What It Does:** Creates and migrates the private SQLite schema for the knowledge graph.

**Used By:** The knowledge repository constructor and knowledge initialization.

**Contract:** Schema initialization is idempotent. It creates durable tables, graph-search tables, seeds structural
ontology rows, materializes discovered `CLS` entities into the `entity_classes` cache, prunes unused non-core
ontology rows, and records schema version.

#### `initialize_schema()`

**What It Does:** Runs the full schema preparation sequence.

**Used By:** Knowledge repository construction.

**Contract:** Accepts a database path, creates parent directories, initializes SQLite settings, creates durable
tables and graph-search tables, seeds ontology primitives, synchronizes dynamic class cache rows from persisted
`CLS` entities, and commits the schema version.

### `core/brain/src/brain/application/knowledge/models/ontology.py`

**What It Does:** Normalizes entity class keys, relation predicate keys, labels, and lifecycle status values.

**Used By:** DTO validators, validation, extraction, repository writes, and query helpers.

**Contract:** Provides an open-world syntax policy. Semantic classes and predicates are allowed when they
normalize into safe lower snake_case keys.

#### `normalize_ontology_key()`

**What It Does:** Converts arbitrary labels into bounded snake_case ontology keys.

**Used By:** Entity class and relation type normalization.

**Contract:** Returns a lowercase identifier no longer than the configured ontology key length.

#### `is_valid_ontology_key()`

**What It Does:** Checks whether a key is syntactically safe for discovered ontology use.

**Used By:** Validation and DTO normalization.

**Contract:** Returns true for lower snake_case identifiers that start with a letter.

### `core/brain/src/brain/application/knowledge/storage/sources.py`

**What It Does:** Discovers memory, diary, profile, and workspace-log sources through the shared source diff
checker.

**Used By:** Dream runs and internal source indexing.

**Contract:** Uses scoped `brain_sources.db` registries to identify changed source mtimes before reading content.
Global scope discovers memory, diary, and profiles. Local scope discovers workspace logs and labels them with
source type workspace_logs. It returns changed source payloads for downstream extraction while the source registry
stores the durable path, mtime, stats, and consumer freshness state.

#### `discover_sources()`

**What It Does:** Finds candidate source files for the selected source family.

**Used By:** Dream source discovery.

**Contract:** Returns source DTOs, filesystem paths, and mtimes without reading unchanged content or writing graph
deltas. The source scope decides whether the source root is shared memory or the active workspace.

#### `ingest_sources()`

**What It Does:** Identifies changed sources and reads only those source files.

**Used By:** Dream runner.

**Contract:** Returns discovered, changed, skipped, deleted, and changed source payload counts for one repository
scope. It compares registry mtimes against the repository scope's `source_consumers` rows and reads file content
only for changed active sources.

#### `check_source_updates()`

**What It Does:** Runs the same mtime comparison without reading source content.

**Used By:** Query-time knowledge graph staleness warnings.

**Contract:** Returns changed and deleted source counts plus paths for the selected scope. It refreshes the
source registry from mtimes, but does not read source content or mutate knowledge graph tables.

#### `mark_source_processed()`

**What It Does:** Marks one source mtime as processed by the knowledge graph consumer.

**Used By:** Dream after a source has been handled by configured model stages.

**Contract:** Writes to the scoped `brain_sources.db` consumer table. It receives the stable source path and mtime
from the registry record and stores them under the `knowledge_graph` consumer.

### `core/brain/src/brain/application/knowledge/pipeline/extraction.py`

**What It Does:** Provides compatibility helpers for source-anchored deltas and multi-stage delta merging.

**Used By:** Dream runner after configured LLM proposal stages return candidate deltas.

**Contract:** Does not emit heuristic graph candidates. Helpers only attach source identifiers, merge returned
model deltas, and preserve the source path/rationale contract.

#### `extract_heuristic_delta()`

**What It Does:** Keeps old imports stable while heuristic extraction is disabled.

**Used By:** Compatibility tests and callers that have not migrated yet.

**Contract:** Accepts source DTO and content, returns an empty knowledge delta with a rationale explaining that
LLM-only extraction is required for structural graph proposals.

#### `merge_deltas()`

**What It Does:** Combines model-backed deltas from multiple configured stages.

**Used By:** Dream runner.

**Contract:** Preserves source path and concatenates entities, relations, schema suggestions, and rationale.
Aliases are not carried forward by the current LLM-only dream contract.

### `core/brain/src/brain/application/knowledge/llm/framing.py`

**What It Does:** Converts raw source content into semantic frames before model-backed extraction.

**Used By:** Dream runner.

**Contract:** Accepts source metadata and raw content, but renders model input without filesystem paths, database
source IDs, line ranges, or source-object instructions. The frame keeps source type internally for harness
selection while the model sees only knowledge-frame kind, title, and text.

#### `build_knowledge_frame()`

**What It Does:** Builds a model-ready knowledge frame from raw content.

**Used By:** Dream runner before LLM calls.

**Contract:** Workspace logs become local change records, diary files become diary records, and generic Markdown
becomes compact sections. The returned DTO records raw character count for diagnostics but does not expose
provenance to the model text.

#### `render_knowledge_frame_for_llm()`

**What It Does:** Renders a knowledge frame as text for LLM prompts.

**Used By:** Dream runner before calling model stages.

**Contract:** Emits knowledge-frame kind, optional title, and semantic text. Source paths and database source IDs
must not appear in the rendered prompt input.

### `core/brain/src/brain/application/knowledge/pipeline/validation.py`

**What It Does:** Filters proposed graph deltas through deterministic rules before persistence.

**Used By:** Dream runner and tests.

**Contract:** Rejects empty names, copied prose labels, invalid ontology keys, missing source IDs, low confidence
records, relations with unresolved endpoint IDs, and predicates that look like embedded entity names instead of
compact verbal nuclei. Compact technical identifiers such as file names, module names, and package-like names are
valid entity labels even when they contain dots. Validation indexes accepted `CLS` class-definition entities before
filtering object entities, and it can also receive run-local known class names from the dream runner. This prevents
false rejection when the LLM returned an object before its same-delta class definition, or when an earlier source in
the same dream cycle already declared the matching `CLS`.

#### `validate_delta()`

**What It Does:** Validates and filters one proposed knowledge delta.

**Used By:** Dream runner.

**Contract:** Returns a validation report DTO with blocking errors, non-blocking warnings, and an accepted delta
containing only applicable records. Class-definition entities are ordered before dependent object entities in the
accepted delta. The optional `known_class_names` argument is a set of PascalCase subtype names already accepted by
the current dream cycle, even if they have not been persisted yet.

#### `known_class_names`

**What It Does:** Carries run-local class definitions into deterministic validation.

**Used By:** The dream runner when processing multiple changed sources in one pass.

**Contract:** Values are PascalCase subtype names accepted from `CLS` entities earlier in the current run or
known before the run started. Validation treats these names like materialized `entity_classes` cache rows for the
purpose of accepting dependent object entities. The set is not a persistence shortcut; a class becomes durable only
when its `CLS` entity is applied and the repository materializes the cache row.

### `core/brain/src/brain/application/knowledge/pipeline/deduplication.py`

**What It Does:** Finds duplicate entities and routes writes through canonical entity records.

**Used By:** Consolidation and tests.

**Contract:** Deduplication is based on normalized labels, entity class, optional legacy aliases, and close string
similarity. It does not delete graph history.

#### `upsert_deduped_entity()`

**What It Does:** Inserts or reuses an entity after duplicate checks.

**Used By:** Consolidation.

**Contract:** Returns the canonical entity identifier. Legacy alias matching can still help resolve older records,
but new LLM dream extraction does not create alias candidates.

### `core/brain/src/brain/application/knowledge/pipeline/consolidation.py`

**What It Does:** Applies validated deltas and promotes recurrent graph relations into consolidated claims.

**Used By:** Dream runner.

**Contract:** Writes only accepted records. Contradictions and replacements should be represented through status
or relations instead of destructive overwrites.

#### `apply_validated_delta()`

**What It Does:** Writes accepted source-anchored entities, resolved ID-to-ID relations, schema suggestions, and
audit records.

**Used By:** Dream confirmation flow and programmatic dream application.

**Contract:** Returns consolidation decision DTOs describing applied work.

#### `promote_recurrent_knowledge()`

**What It Does:** Promotes repeated graph relations into consolidated claims.

**Used By:** Dream confirmation flow and programmatic dream application.

**Contract:** Requires support from at least the configured number of distinct sources.

#### `persist_validation_report()`

**What It Does:** Stores pending delta and validation report payloads.

**Used By:** Dream proposal flow and programmatic dream application.

**Contract:** Always records proposed deltas for auditability before optional application.

### `core/brain/src/brain/application/knowledge/pipeline/delta_application.py`

**What It Does:** Applies reviewed pending deltas after revalidation.

**Used By:** Dream bootstrap/application flow and knowledge delta review commands.

**Contract:** Reads accepted pending-delta payloads, revalidates them against the current repository contract,
sorts `CLS` class-definition deltas before dependent object deltas, writes accepted records through consolidation,
updates proposal status, and promotes recurrent knowledge after successful writes. It never applies a row that no
longer validates.

#### `ApplicationEventCallback`

**What It Does:** Defines the verbose diagnostic event sink for delta application.

**Used By:** Dream console logging when `--verbose-log` is enabled.

**Contract:** Receives JSON-compatible dictionaries for application batch start, delta start, validation start,
validation result, write start, delta applied, delta failed, promotion start, promotion result, and batch complete.
The callback is observational and must not mutate graph state.

#### `apply_pending_delta_rows()`

**What It Does:** Applies selected pending delta rows.

**Used By:** Dream bootstrap/application flow and knowledge delta review commands.

**Contract:** Accepts a repository, selected row dictionaries, and an optional application event callback. Returns
applied count, application error strings, and consolidation decisions. Failed selected rows are marked failed so
operators can inspect or delete them later.

### `core/brain/src/brain/application/knowledge/llm/client.py`

**What It Does:** Calls configured OpenAI-compatible model stages and parses responses into knowledge deltas.

**Used By:** Dream runner when model-backed stages are enabled.

**Contract:** Loads stage config, resolves environment-referenced API keys, sends a chat completion request over
semantic frame text, strips JSON fences or parses compact relation triplets by stage, sanitizes model output, and
validates it against the knowledge delta DTO. Optional event callbacks receive live diagnostics for stage start,
HTTP response, parsed success, and failures. Diagnostics include stage name, model name, provider endpoint, source
path, prompt template path, prompt size, output size, elapsed time, parsed output, and delta counts, but never API
keys or prompt content. Failures are returned to the runner as warnings unless the caller invokes one stage
directly.

#### `LLMEventCallback`

**What It Does:** Defines the live diagnostic event sink used by model-backed knowledge stages.

**Used By:** Dream runner and dream command console logging when `--verbose-log` is enabled.

**Contract:** Receives JSON-compatible dictionaries. Known event names are stage_start, http_response,
stage_success, and stage_error. The callback is advisory and must not mutate graph state. The normal dream CLI
review does not attach this callback; JSON mode also leaves it detached to preserve machine-readable output.
When attached by `--verbose-log`, stage_start reports the Markdown prompt template path instead of dumping prompt
content.

#### `generate_delta_with_llm()`

**What It Does:** Runs one configured model-backed stage.

**Used By:** Multi-stage generation.

**Contract:** Raises a knowledge LLM error when the stage is disabled, missing credentials, unavailable, or returns
invalid output for that stage. Entity detection keeps only entities and receives an entity-class catalog based on
spaCy base labels, known subtypes, and `CLS` class-definition entities. Relation extraction expects compact triplet
lines in the compact triplet form; exact names are resolved to internal endpoint IDs
before DTO validation. Aliases, source anchoring, numeric endpoint fields, and unsupported fields emitted by the
model are discarded. When an event callback is supplied, it emits request diagnostics before the request, HTTP
diagnostics after the provider responds, parsed output diagnostics after valid DTO parsing, and error diagnostics
on request or parsing failures. Request diagnostics include the prompt template path and prompt size, not the
prompt text.

#### `("subject_name","predicate","object_name")`

**What It Does:** Defines the compact relation proposal syntax returned by the relation extraction LLM stage.

**Used By:** The relation extraction prompt, LLM output parser, and sanitizer that converts exact endpoint names
into local or persisted relation endpoint IDs.

**Contract:** Each line contains exactly one quoted subject name, predicate, and object name. Subject and object
must match entity canonical names already present in the current delta or persisted graph context. The predicate
is a compact verbal relation key, not an entity name and not a sentence.

#### `generate_multistage_deltas()`

**What It Does:** Runs the configured model stages in order.

**Used By:** Dream runner.

**Contract:** Returns successful stage deltas plus warning strings for failed stages. The hidden
`entity_name_to_id` resolver lets relation extraction use exact entity names while the harness converts them to
IDs. Entity detection stage output receives harness-only local candidate IDs before relation extraction runs, but
those IDs are stripped from the relation prompt. The `entity_class_catalog` argument is consumed by NER prompts so
independent frames can reuse base classifiers and known subtypes. Merge-like stages do not need that dictionary
because classifier semantics are already present on entities. The optional event callback is forwarded to each
stage so a caller can observe every external model call in real time.

#### `entity_name_to_id`

**What It Does:** Carries the hidden exact-name resolver used after relation extraction returns endpoint names.

**Used By:** The LLM client sanitizer during relation extraction.

**Contract:** Maps canonical persisted entity names to persisted entity IDs. During relation sanitization, this
resolver is combined with the current delta's local candidate IDs. Neither resolver is rendered in the prompt; it
exists so the model can stay name-oriented while the repository remains ID-oriented.

#### `entity_class_catalog`

**What It Does:** Carries the classifier vocabulary used by the entity-detection stage.

**Used By:** Multi-stage LLM generation during NER.

**Contract:** The catalog is a read-only mapping from classifier key to description. The harness builds it from
the stable spaCy base labels, persisted entity-class rows, persisted class-definition entities, and `CLS` entities
validated earlier in the same dream run. It is sent only to the entity detection stage because that stage must
decide whether to reuse an existing subtype or introduce a new class-definition entity. Merge, consolidation, and
relation extraction stages do not need a separate classifier dictionary because their inputs already carry the
classifier on each entity. Validation receives the catalog as run-local known class names.

The catalog is advisory for the model and contractual for validation. If the model emits a new subtype, the
same entity-detection delta must include a matching `CLS` class-definition entity or reference a subtype already
materialized in `entity_classes`. If the subtype is invalid or unsupported, deterministic validation rejects that
part of the delta.

#### `build_delta_prompt()`

**What It Does:** Builds the source, prior-delta, graph-context, and ontology-policy prompt for one stage.

**Used By:** LLM stage execution.

**Contract:** Produces plain text that requests JSON owned by the active stage. Entity prompts include the
classifier catalog and require class discoveries to appear as `CLS` entities. Relation prompts expose entity names
without local IDs and require name-based endpoints rather than numeric endpoint references.

### `core/brain/prompts/`

**What It Does:** Stores Markdown prompt templates for the knowledge LLM stages.

**Used By:** The prompt loader and the LLM client.

**Contract:** The directory separates prompt wording from Python logic. Each template is plain Markdown, contains
the required sections for the loader, and may use double-brace placeholders rendered by the local harness.

#### `common_delta.md`

**What It Does:** Defines the shared knowledge-delta prompt body used across stages.

**Used By:** `render_stage_prompt()`.

**Contract:** Contains the common ontology policy, JSON output rules, graph context block, classifier catalog
block, prior delta block, and content block. Stage-specific sections are inserted into this template before the
model call.

#### `<stage_name>.md`

**What It Does:** Defines one stage-specific prompt template.

**Used By:** `get_stage_system_prompt()` and `render_stage_prompt()`.

**Contract:** Must include `## System Prompt`, `## Stage Objective`, and `## Stage Output Policy`. The filename
matches the configured stage name, such as `entity_detection.md` or `relation_extraction.md`.

#### `entity_detection.md`

**What It Does:** Defines the NER stage wording.

**Used By:** Entity detection LLM calls.

**Contract:** Limits output to entity proposals, asks the model to reuse known classifier names, and requires
new dynamic subtypes to appear as `CLS` entities with PascalCase names.

#### `relation_extraction.md`

**What It Does:** Defines the relation stage wording.

**Used By:** Relation extraction LLM calls.

**Contract:** Limits output to relation proposals, requires exact endpoint names from prior deltas or graph
context, and forbids numeric endpoint IDs.

### `core/brain/prompts/__init__.py`

**What It Does:** Loads Markdown prompt templates and renders stage-specific prompt sections into the common
knowledge-delta prompt.

**Used By:** The LLM client when building system prompts and user prompts for configured knowledge stages.

**Contract:** Prompt files live in `core/brain/prompts/` and use second-level sections named `System Prompt`,
`Stage Objective`, and `Stage Output Policy`. The loader extracts those sections, renders double-brace
placeholders with runtime values, and falls back to the consolidation template when a configured stage has no
dedicated file.

#### `get_stage_system_prompt()`

**What It Does:** Returns the `System Prompt` section for one stage template.

**Used By:** `generate_delta_with_llm()` when constructing the chat-completions system message.

**Contract:** Accepts a stage name, resolves `<stage_name>.md` under `core/brain/prompts/`, and returns plain
prompt text. Missing stage files use the default consolidation prompt.

#### `render_stage_prompt()`

**What It Does:** Combines `common_delta.md` with the active stage template and runtime values.

**Used By:** `build_delta_prompt()`.

**Contract:** Accepts a stage name and a dictionary of string values. It renders stage-local placeholders before
inserting those sections into the common prompt, so limits, graph context, prior deltas, classifier catalogs, and
content stay outside Python logic.

### `core/brain/src/brain/application/knowledge/orchestration/dream.py`

**What It Does:** Orchestrates changed-source discovery, configured LLM proposals, deterministic validation,
pending delta persistence, optional programmatic application, and recurrent promotion.

**Used By:** The dream command and tests.

**Contract:** The CLI uses a proposal-first review flow. Programmatic callers can still request application
through the run method, but model output remains advisory and never writes directly to the database.

#### `DreamRunner`

**What It Does:** Holds the repository dependency and runs one consolidation pass.

**Used By:** The dream command.

**Contract:** Constructed with a knowledge repository. Its run method returns a dream run DTO and records a run
summary in the database.

#### `DreamRunner.run()`

**What It Does:** Executes one dream consolidation pass.

**Used By:** Dream command action.

**Contract:** Accepts domain, limit, proposal-only state, compatibility LLM flag, optional confidence override, and
optional LLM event callback. The runner operates against the repository scope supplied at construction time. It
loads model configuration from the global config, builds semantic knowledge frames before model calls, and keeps
source provenance in local metadata. It also builds a read-only graph-name context and a hidden exact-name
resolver for relation endpoint conversion. It carries a run-local classifier catalog forward across changed
sources, so accepted `CLS` declarations become valid schema for later sources in the same pass. Returns a dream
run DTO including pending delta IDs written for review. When model stages are unavailable, it records warnings and
does not create heuristic replacement proposals.

### `core/brain/src/brain/application/knowledge/presentation/rendering.py`

**What It Does:** Converts persisted delta proposal rows into human-readable terminal review text.

**Used By:** Dream and knowledge delta review commands.

**Contract:** Rendering is read-only. It uses semantic sections instead of generic `key=value` formatting.
Proposed counts, accepted counts, error count, and warning count render on separate lines. The metric legend maps
Et to entities, Re to relations, Ale to legacy/manual aliases, and Sch to schema suggestions. Live text values are
always wrapped in double quotes and use the blue terminal role when color is enabled.

#### `render_delta_review()`

**What It Does:** Renders a list of proposal rows with state, source, counts, rationale, entities, relations,
schema suggestions, errors, and warnings.

**Used By:** Dream and knowledge delta review commands.

**Contract:** Accepts parsed repository rows, color state, title text, compact mode, optional review hint, and
optional persisted entity rows used to render relation endpoints as entity labels. It returns terminal text and
does not mutate repository state.

#### `is_delta_applicable()`

**What It Does:** Determines whether a proposal row can be selected for application.

**Used By:** Dream confirmation logic and renderer state labels.

**Contract:** Returns true only when deterministic validation is valid and accepted records remain.
Legacy deltas from retired contracts return false and are hidden from application.

#### `is_delta_legacy()`

**What It Does:** Determines whether a pending delta row uses a retired payload contract.

**Used By:** Knowledge delta deletion and renderer state checks.

**Contract:** Returns true for deterministic fallback deltas, source-document entities, retired relation fields,
or deltas missing required source and endpoint IDs.

### `core/brain/src/brain/application/knowledge/querying/query.py`

**What It Does:** Provides KG-only query behavior.

**Used By:** Knowledge query command and global query service.

**Contract:** Reads graph entities and evidence through repository-backed views and can optionally include hybrid
memory vector results.

#### `query_knowledge()`

**What It Does:** Searches the knowledge graph backend.

**Used By:** Knowledge query command and global query service.

**Contract:** Accepts repository, text, limit, and hybrid flag. Returns JSON-compatible result dictionaries.

### `core/brain/src/brain/application/knowledge/presentation/views.py`

**What It Does:** Builds read-only graph views for search, entity inspection, relation listing, and recurrent
relation detection.

**Used By:** Repository facade methods, knowledge query, knowledge show, export, and consolidation.

**Contract:** Uses repository sessions for read queries and returns JSON-compatible dictionaries.

#### `search_repository()`

**What It Does:** Searches entity and evidence graph-search tables.

**Used By:** Repository search facade.

**Contract:** Returns ranked graph result dictionaries.

#### `get_entity_view()`

**What It Does:** Builds one entity view with aliases and outgoing relations.

**Used By:** Knowledge show command.

**Contract:** Accepts ID, canonical name, or alias reference.

### `core/brain/src/brain/application/knowledge/presentation/export.py`

**What It Does:** Exports graph entities and relations as JSON-LD.

**Used By:** Knowledge export command.

**Contract:** Returns a JSON-compatible JSON-LD document with context and graph nodes.

#### `export_jsonld()`

**What It Does:** Builds a JSON-LD graph export from repository views.

**Used By:** Knowledge export command.

**Contract:** Reads entities and relations and returns a dictionary that can be serialized directly.

## Repository Contracts:

### `core/brain/src/brain/application/knowledge/storage/repository.py`

**What It Does:** Owns SQLite persistence for the private knowledge graph.

**Used By:** Knowledge commands, dream runner, query services, consolidation, views, and export.

**Contract:** Opens configured SQLite connections, initializes schema on construction, provides transaction-safe
methods for source identity, evidence, entity, alias, relation, ontology suggestion, delta, and dream run
persistence. It does not own source mtime or processed-state tracking.

#### `KnowledgeRepository`

**What It Does:** Provides the persistence boundary for the knowledge graph.

**Used By:** Knowledge commands and knowledge services.

**Contract:** Construction resolves scope, shared config, database path, and schema readiness. `global` writes to
the global database; `local` writes to the workspace database. Methods return IDs or JSON-compatible dictionaries
and never expose raw cursor state to callers.

#### `KnowledgeRepository.status()`

**What It Does:** Reports schema version, database path, and row counts.

**Used By:** Knowledge status and initialization commands.

**Contract:** Returns a JSON-compatible status dictionary.

#### `KnowledgeRepository.upsert_source()`

**What It Does:** Inserts or updates one stable source identity row.

**Used By:** Dream and consolidation workflows that need a source identity anchor.

**Contract:** Deduplicates by stable source path and returns the source ID. The row contains source type, path,
title, and active state only; filesystem mtimes and processed timestamps are JSON-owned contracts.

#### `KnowledgeRepository.add_evidence()`

**What It Does:** Inserts or reuses one evidence quote.

**Used By:** Consolidation.

**Contract:** Deduplicates by quote hash, refreshes the evidence graph-search row, and returns the evidence ID.

#### `KnowledgeRepository.upsert_entity()`

**What It Does:** Inserts or updates one entity.

**Used By:** Deduplication and consolidation.

**Contract:** Deduplicates by entity class and normalized name, refreshes the entity graph-search row, and returns
the entity ID.

#### `KnowledgeRepository.add_alias()`

**What It Does:** Inserts or reuses an alias for an entity.

**Used By:** Deduplication and consolidation.

**Contract:** Deduplicates by entity and normalized alias.

#### `KnowledgeRepository.find_entity_by_ref()`

**What It Does:** Resolves entity references by ID, canonical name, or alias.

**Used By:** Relation writes, knowledge show, and consolidation.

**Contract:** Returns the best non-merged entity row or none.

#### `KnowledgeRepository.upsert_relation()`

**What It Does:** Inserts or reuses one relation.

**Used By:** Consolidation.

**Contract:** Requires `source_id`, `subject_id`, `object_id`, `predicate`, and `confidence`. It resolves both
endpoint IDs to existing entities, deduplicates by source and subject-predicate-object tuple, and returns the
relation ID.

#### `KnowledgeRepository.record_pending_delta()`

**What It Does:** Stores a proposed delta and validation report.

**Used By:** Dream runner.

**Contract:** Writes JSON payloads to the pending delta table and returns the row ID.

#### `KnowledgeRepository.list_pending_deltas()`

**What It Does:** Lists persisted delta proposals with parsed payload and validation JSON.

**Used By:** Knowledge delta review command and dream command presentation.

**Contract:** Joins proposal rows to their source metadata, filters by status unless all is requested, orders newest
first, and returns JSON-compatible dictionaries.

#### `KnowledgeRepository.get_pending_delta()`

**What It Does:** Reads one persisted delta proposal with parsed payload and validation JSON.

**Used By:** Knowledge delta review command and dream command presentation.

**Contract:** Returns one JSON-compatible row by identifier or none when the proposal does not exist.

#### `KnowledgeRepository.update_pending_delta_status()`

**What It Does:** Updates the lifecycle status for one persisted proposal.

**Used By:** Dream confirmation flow and programmatic dream application.

**Contract:** Stores normalized lowercase status values such as pending, applied, rejected, or failed.

#### `KnowledgeRepository.delete_pending_deltas()`

**What It Does:** Deletes persisted pending delta proposal rows by ID.

**Used By:** Knowledge delta deletion command.

**Contract:** Accepts explicit `pending_deltas` IDs, deletes matching rows in one transaction, and returns the
number of removed rows.

#### `KnowledgeRepository.record_applied_delta()`

**What It Does:** Stores an applied delta audit record.

**Used By:** Confirmed consolidation writes.

**Contract:** Writes the accepted applied payload and returns the row ID.

#### `KnowledgeRepository.record_dream_run()`

**What It Does:** Stores a dream consolidation summary.

**Used By:** Dream runner.

**Contract:** Writes start, finish, status, proposal-only state, counts, errors, and summary.

#### `KnowledgeRepository.add_schema_suggestion()`

**What It Does:** Stores an ontology evolution suggestion.

**Used By:** Consolidation.

**Contract:** Deduplicates by suggestion type and normalized name, records confidence, and leaves the suggestion
pending unless later approved.

#### `KnowledgeRepository.ensure_entity_class()`

**What It Does:** Ensures a discovered entity class exists in the ontology registry.

**Used By:** Entity writes and consolidation.

**Contract:** Inserts or updates a cache row for a core class or a discovered PascalCase subtype. Dynamic rows are
materialized from `CLS` entities and are used by validation and prompt catalogs as a fast class lookup.

#### `KnowledgeRepository.ensure_relation_type()`

**What It Does:** Ensures a discovered relation type exists in the ontology registry.

**Used By:** Relation writes and consolidation.

**Contract:** Inserts a normalized relation key only when absent.
