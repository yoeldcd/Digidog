<!-- Author: Yoel David <yoeldcd@gmail.com> | X: https://x.com/SAY6267 -->

# Brain Security Model

## Index:
- [Authentication Model](#authentication-model)
- [Authorization Matrix](#authorization-matrix)
- [Data Privacy Constraints](#data-privacy-constraints)

## Authentication Model:
The Brain subsystem is a local CLI runtime. It does not implement user accounts, sessions, roles, or remote
authentication. The local operating-system account and the workspace filesystem permissions are the trust boundary.

External model calls use provider API keys from environment-referenced configuration values. The runtime
configuration may store environment variable references, but it must not store raw provider secrets in versioned
source files.

## `brain.local-runtime`

### Authorization Matrix:

| Resource / Action | Administrator | Developer | User | Guest |
|---|---|---|---|---|
| Read Markdown memory | Yes | Yes | Yes | No |
| Write Markdown memory through CLI | Yes | Yes | Yes | No |
| Initialize private knowledge runtime | Yes | Yes | Yes | No |
| Reset private knowledge database | Yes | Yes, with confirmation | No | No |
| Prune and recreate knowledge graph | Yes | Yes, with exact confirmation | No | No |
| Run dream proposal review | Yes | Yes | Yes | No |
| Confirm selected dream deltas | Yes | Yes, interactively | No | No |
| Delete unwanted knowledge deltas | Yes | Yes, with confirmation | No | No |
| Configure external LLM stage keys | Yes | Yes | No | No |
| Commit source code | Yes | Yes | No | No |
| Commit private runtime data | No | No | No | No |

### Data Privacy Constraints:
Markdown memory, diary records, workspace logs, and the knowledge graph may contain sensitive context. Runtime
graph data is private local state and is intentionally separated from versioned code. The global graph stores
shared-home knowledge; the local graph stores active-workspace knowledge.

#### `.gitignore`

**What It Does:** Prevents private runtime graph data from being tracked by the repository.

**Used By:** Git status, commits, and repository hygiene checks.

**Contract:** The root ignore rules must include the global private database runtime directory and the local
`$agent/database` runtime directory. The code package remains versioned, but runtime database files remain
ignored.

#### `database/.gitignore`

**What It Does:** Adds a local defense-in-depth ignore rule inside each private database runtime folder.

**Used By:** Brain database path initialization.

**Contract:** It ignores every file inside the runtime folder except the local ignore file itself. This protects
knowledge databases, source registries, vectorstore files, exports, sidecars, or model-stage scratch files from
accidental staging.

#### `database/`

**What It Does:** Names the private runtime directory used by current brain stores.

**Used By:** Database path helpers, knowledge repositories, source registries, vectorstore managers, and session
initialization.

**Contract:** This directory is runtime state, not source code. The global instance is `core/database`; the local
workspace instance is `$agent/database`. Both directories must remain ignored except for their defensive
`.gitignore` files.

#### `core/database`

**What It Does:** Stores shared-home private runtime databases and vector indexes.

**Used By:** Global knowledge graph, global source registry, avatar runtime storage, and global vectorstores.

**Contract:** It is the durable core runtime root. Its database families have
fixed subdirectories and are not selected by fields in `brain_configs.json`.

#### `$agent/database`

**What It Does:** Stores active-workspace private runtime databases and vector indexes.

**Used By:** Local knowledge graph, local source registry, local log vectorstore, and repo-scoped query paths.

**Contract:** It is isolated per workspace. Runtime files inside it should not be copied to other repos unless an
operator intentionally migrates workspace state.

#### `core/configs/brain_configs.json`

**What It Does:** Stores the single unified brain configuration for memory/vector settings and knowledge model
stages.

**Used By:** Knowledge config loading, LLM stage execution, and dream consolidation.

**Contract:** The file may contain model names, base URLs, stage enablement, token limits, temperature, confidence
thresholds, and environment variable references. It must not contain raw provider secrets when versioned or shared.
The local workspace graph runtime must not maintain a second config file.

#### `brain_configs.json`

**What It Does:** Names the unified brain config file independently of its global directory.

**Used By:** Documentation tables and config DTO references that discuss the filename rather than the full path.

**Contract:** The canonical file path is `core/configs/brain_configs.json`.

#### `core/database/knowledge/brain_knowledge.db`

**What It Does:** Stores the global private SQLite knowledge graph.

**Used By:** Knowledge repository, query, export, and dream consolidation.

**Contract:** The database is runtime state, not source code. It stores shared memory, diary, and profile-derived
graph state. It must remain outside versioned source control and must be reset only by explicit command intent.

#### `brain_knowledge.db`

**What It Does:** Names the global knowledge graph SQLite database file.

**Used By:** Runtime path helpers and the global knowledge repository.

**Contract:** The filename and its `core/database/knowledge` parent are fixed by
the core directory contract. Local workspace KG storage uses `$agent/database/sources.db`.

#### `$agent/database/sources.db`

**What It Does:** Stores the local private SQLite knowledge graph for the active workspace.

**Used By:** Local knowledge repository scope, query, export, and dream consolidation over workspace-local sources.

**Contract:** The database is runtime state, not source code. It stores local graph state such as workspace log
knowledge. It must remain outside versioned source control and must be reset only by explicit command intent.

#### `brain_sources.db`

**What It Does:** Stores the scoped source registry and per-consumer processed mtimes.

**Used By:** Query freshness checks, dream source selection, memory structure summaries, and log source tracking.

**Contract:** The global registry lives at `core/database/sources/brain_sources.db`; the local registry lives at
`$agent/database/brain_sources.db`. Registry rows include path, source type, title, mtime, lightweight stats,
active state, and consumer processing state. These databases are private runtime state and must not be staged.

#### `core/database/sources/brain_sources.db`

**What It Does:** Stores the global source registry for shared memory, diary, profiles, and future global source
families.

**Used By:** Global query freshness checks, global dream source selection, and memory structure summaries.

**Contract:** It stores source mtimes and consumer processed mtimes. It replaces retired memory JSON indexes as
the machine-readable source catalog.

#### `$agent/database/brain_sources.db`

**What It Does:** Stores the local source registry for workspace-owned source families such as logs.

**Used By:** Local query freshness checks, local dream source selection, and log registry refreshes.

**Contract:** It is scoped to the active repo and should not be shared across workspaces.

#### `brain_vectorstore`

**What It Does:** Stores the scoped embedding/vector indexes.

**Used By:** Memory vector search, local log vector search, and hybrid query paths.

**Contract:** The global vectorstore lives at `core/database/vectorstores`; the local vectorstore lives at
`$agent/database/brain_vectorstore`. Vectorstore files are derived private runtime state.

#### `core/database/vectorstores`

**What It Does:** Stores the global ChromaDB vectorstore used for shared memory search.

**Used By:** Memory vector search, hybrid query, vectorstore update, and vectorstore status commands.

**Contract:** The location is fixed by core topology. Legacy agent-home
vectorstores are not consulted by the migrated Brain.

#### `$agent/database/brain_vectorstore`

**What It Does:** Stores the local ChromaDB vectorstore used for workspace log search.

**Used By:** Log query, append-log indexing, edit-log indexing, local vectorstore rebuild, and local vectorstore
status commands.

**Contract:** It supersedes the retired `$agent/data/vectorstore` location.

#### `$agent/data/knowledge/knowledge.db`

**What It Does:** Names a retired local knowledge database location accepted only as migration input.

**Used By:** `brain init` runtime migration.

**Contract:** If the current target is absent, the migrator moves this file to `$agent/database/sources.db`.

#### `$agent/data/knowledge/angi_kg.sqlite3`

**What It Does:** Names an older retired local KG filename accepted only as migration input.

**Used By:** `brain init` runtime migration.

**Contract:** It follows the same safety rules as `$agent/data/knowledge/knowledge.db`.

#### `$agent/data/vectorstore`

**What It Does:** Names the retired local log vectorstore directory accepted only as migration input.

**Used By:** `brain init` runtime migration.

**Contract:** It moves to `$agent/database/brain_vectorstore` only when the new target is absent or empty.

#### `source_state.json`

**What It Does:** Names a retired per-consumer freshness file accepted only as migration input.

**Used By:** `brain init` runtime migration.

**Contract:** Its source path mtimes are imported into `brain_sources.db` consumer rows and the file is then
removed. New code must not create it.

#### `OPENROUTER_API_KEY`

**What It Does:** Supplies credentials for OpenRouter-compatible model calls when the runtime config references
that environment variable.

**Used By:** The knowledge LLM client.

**Contract:** The key is resolved at runtime from the process environment. If the value is not resolved, model
stages fail closed with a warning or explicit LLM error.

## `brain.application.knowledge-llm`

### Authorization Matrix:

| Resource / Action | Administrator | Developer | User | Guest |
|---|---|---|---|---|
| Configure model-backed dream stages | Yes | Yes | No | No |
| Send source excerpts to external LLM | Yes | Yes, when stage config is enabled and credentials are present | No | No |
| Apply model-proposed deltas directly | No | Only human-mode empty-graph bootstrap after validation | No | No |
| Persist accepted validated deltas | Yes | Yes, with interactive selection or human-mode empty-graph bootstrap | No | No |
| Create database tables from model output | No | No | No | No |

### Data Privacy Constraints:
External LLM calls are controlled by per-stage configuration and credentials. Ingestion, deterministic validation,
query, and export can run without sending source content to an external provider, but `dream` does not generate
heuristic graph replacement deltas when no model stage can return a valid proposal.

Model stages receive semantic knowledge-frame text, a compact read-only graph-name context, and prior delta JSON
with endpoint IDs removed from relation-facing prompts. They do not receive filesystem paths or database source IDs
as knowledge, and relation extraction is asked for exact `subject_name` and `object_name` values rather than
numeric endpoint IDs. Their output is advisory. The validation layer checks confidence, ontology key syntax,
relation endpoint resolution, predicate shape, and source anchoring before any proposal can be applied.

Schema evolution is constrained to suggestions. A model can propose entity class or relation type keys, but it
cannot create SQLite tables, alter migrations, bypass validation, or delete graph history.

## `brain.destructive-actions`

### Authorization Matrix:

| Resource / Action | Administrator | Developer | User | Guest |
|---|---|---|---|---|
| Delete memory entry | Yes | Yes | Yes | No |
| Delete memory domain | Yes | Yes, with exact confirmation | No | No |
| Rebuild shared vectorstore | Yes | Yes, with confirmation | No | No |
| Rebuild local vectorstore | Yes | Yes, with confirmation | No | No |
| Reset knowledge database | Yes | Yes, with confirmation | No | No |
| Prune knowledge graph before dream | Yes | Yes, with exact confirmation | No | No |
| Delete knowledge deltas | Yes | Yes, with confirmation or reviewed `--yes` | No | No |

### Data Privacy Constraints:
Destructive operations require explicit user intent. Recursive memory domain deletion requires a matching
confirmation value. Vectorstore rebuilds, knowledge database reset, and knowledge delta deletion expose
non-interactive confirmation only for automation that has already reviewed the action. The dream prune flow does
not accept a non-interactive bypass; it prints the current graph status and requires the exact confirmation
RECREATE.

The dream write path is intentionally separated from proposal generation. Dream first records pending proposals and
validation reports, then an interactive prompt must receive `y` or explicit delta numbers before accepted records
are written. The exception is first-population bootstrap in human output mode: when a scoped graph has no entities
or relations, validated deltas from the first run are applied automatically so the graph can start with usable
class and entity anchors. JSON mode keeps proposal inspection read-only. Model output still cannot bypass
deterministic validation.
