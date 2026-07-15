# Brain CLI Commands

## Index:
- [CLI Architecture](#cli-architecture)
- [Global Flags](#global-flags)
- [Commands Index](#commands-index)
- [Command Details](#command-details)
- [Flag Details](#flag-details)

## CLI Architecture:
The Brain CLI is composed from declarative command modules and executable action modules. Each command module
declares a schema with its command name, domain, help text, positional arguments, options, and defaults. The
parser builds `argparse` contracts from those schemas, and the router dispatches the parsed namespace to the
matching action handler from `brain.presentation.actions.registry`.

The command layer is intentionally an adapter layer. Commands validate terminal inputs, call domain services or
repositories, and format human or JSON output. Storage rules, SQLite migrations, knowledge graph validation,
vectorstore maintenance, and memory indexing stay in their own modules.

## Global Flags:

| Flag | Type | Description |
|---|---|---|
| `--color` | boolean | Enables ANSI color for terminal output after the router strips the flag from the command-specific parser input. |
| `--verbose-log` | boolean | Enables diagnostic progress output with the concrete objects touched by commands that read the router-level verbose setting. |

## Commands Index:

| Command | Arguments | Flags | Description |
|---|---|---|---|
| `help` | topic | `--short` | Shows dynamically generated help for the available command registry. |
| `init` | none | `--limit-diary` | Migrates runtime stores, runs workspace checks, updates indexes, prepares knowledge runtime, and hydrates context. |
| `get-context` | none | `--limit-diary` | Prints the context hydration payload without the full initialization sequence. |
| `check-workspace` | none | `--json` | Validates memory structure and nesting compliance. |
| `create-brain` | workspace_path | `--workspace`, `--limit` | Creates a local workspace brain wrapper and supporting directories. |
| `query` | domain, query | `--limit`, `--source`, `--scope`, `--mechanism`, `--knowledge-scope`, `--deep`, `--explain`, `--json` | Searches memory and knowledge through the global query point. |
| `serve-explorer` | none | `--host`, `--port`, `--api-timeout` | Serves the Brain Explorer static UI and local JSON API. |
| `wiki` | mode, documentation_path | `--log-domain`, `--host`, `--port`, `--json` | Checks, generates, or serves a documentation wiki through the core-owned utility. |
| `propagate-agent-prompt` | none | `--source`, `--mirrors-file`, `--dry-run`, `--json` | Verifies or synchronizes canonical prompt mirrors through the core-owned utility. |
| `memory-structure` | none | `--json`, `--uptime-order`, `--limit` | Lists memory domains, subdomains, and indexed entries. |
| `add-memory-domain` | domain | `--json` | Creates a Markdown memory domain or subdomain. |
| `set-memory-entry` | domain, key, val | `--value`, `--json` | Writes Markdown content to a memory entry. |
| `get-memory-entry` | domain, key | `--json`, `--full-text`, `--uptime-order`, `--limit` | Reads one memory entry or a memory domain tree. |
| `delete-memory-entry` | domain, key | `--confirm`, `--json` | Deletes a memory entry or confirmed memory domain. |
| `export` | domain, out_dir | `--out` | Exports memory content. |
| `update-memory-index` | none | `--json` | Refreshes the SQLite memory source registry. |
| `write-diary` | body | `--datetime`, `--title`, `--text` | Creates a diary entry. |
| `read-diary` | date | `--datetime`, `--time`, `--limit` | Reads diary entries by date and optional exact minute. |
| `edit-diary` | timestamp, body | `--datetime`, `--title`, `--text`, `--append`, `--replace`, `--with-text` | Edits a diary entry. |
| `append-log` | compact fields | `--log-domain`, `--title`, `--type`, `--why`, `--desc`, `--impact`, `--datetime` | Appends a structured workspace log entry. |
| `edit-log` | timestamp, compact fields | `--datetime`, `--log-domain`, `--title`, `--type`, `--why`, `--desc`, `--impact` | Edits an existing workspace log entry. |
| `log-index` | section | none | Displays the log index, optionally filtered by domain. |
| `update-log-index` | mode | `--fix` | Rebuilds the log indexes and can migrate legacy logs. |
| `read-log` | date | `--datetime`, `--time`, `--limit` | Reads log entries for one date and optional exact minute. |
| `export-logs` | none | `--stdout`, `--files`, `--zip`, `--domain`, `--date`, `--time`, `--from`, `--to`, `--output` | Exports DB-backed logs to stdout by default; persistent targets are migration-only artifacts. |
| `query-log` | domain, query | `--limit`, `--json` | Searches workspace logs through the local log vectorstore. |
| `list-profiles` | none | `--json` | Lists available agent profiles. |
| `read-profile` | name | `--json` | Reads every Markdown entry for one profile. |
| `list-snippets` | query | `--filter` | Lists reusable snippets from the shared home repository. |
| `clone-snippet` | name | `--dest` | Copies a reusable snippet into the workspace. |
| `update-vectorstore` | none | `--json` | Incrementally updates the shared memory vectorstore. |
| `rebuild-vectorstore` | none | `--yes`, `--json` | Rebuilds the shared memory vectorstore from scratch. |
| `vectorstore-status` | none | `--json` | Prints shared vectorstore status. |
| `rebuild-local-vectorstore` | none | `--yes`, `--collection`, `--json` | Rebuilds a local vector collection. |
| `local-vectorstore-status` | none | `--json` | Prints local vectorstore status. |
| `show-backlog` | task_domain | none | Displays the task backlog tree. |
| `add-task` | task_domain, title_pos, description_pos | `--title`, `--description`, `--priority` | Adds a backlog task. |
| `task-finished` | task_id | none | Compatibility alias that marks a backlog task DONE. |
| `set-task-status` | task_id, status | none | Sets a backlog task to WORKING or DONE. |
| `edit-task` | task_id | `--title`, `--description`, `--priority` | Edits fields while preserving task state. |
| `delete-task` | task_id | `--force` | Deletes a DONE task, or force-deletes a WORKING task. |
| `knowledge-init` | none | `--scope`, `--reset`, `--yes`, `--json` | Initializes global and local knowledge graph runtimes. |
| `knowledge-status` | none | `--scope`, `--json` | Reports scoped knowledge graph configuration and database counts. |
| `knowledge-deltas` | none | `--scope`, `--id`, `--yes`, `--limit`, `--status`, `--json` | Reviews persisted knowledge delta proposals and confirms application. |
| `delete-knowledge-deltas` | ids | `--scope`, `--all`, `--legacy`, `--status`, `--limit`, `--yes`, `--json` | Deletes unwanted knowledge delta proposals. |
| `knowledge-query` | query | `--scope`, `--limit`, `--hybrid`, `--explain`, `--json` | Searches the knowledge graph backend directly. |
| `knowledge-show` | entity | `--entities`, `--relations`, `--classes`, `--filter`, `--scope`, `--json` | Shows graph records or one scoped knowledge graph entity view. |
| `knowledge-export` | none | `--scope`, `--format`, `--json` | Exports scoped knowledge graphs as JSON-LD. |
| `dream` | none | `--scope`, `--domain`, `--limit`, `--llm`, `--min-confidence`, `--prune`, `--json`, `--verbose-log` | Uses configured LLM stages to propose cognitive deltas for selected source scopes, bootstraps empty graphs, and asks which remaining deltas to apply. |

## Command Details:

## `brain.general`

### Commands Index:
General commands initialize the workspace, validate structure, create workspace wrappers, and provide the global
query entry point.

### Command Details:

#### `help`

**What It Does:** Prints the dynamically generated command help surface. It reads the registered command schemas
instead of maintaining a separate static command list.

**Use It When:** You need a quick terminal reminder of available commands, compact usage patterns, or a domain
index. Use `help --short` when you only want domains and command names.

**Result:** Prints help text and does not modify workspace state. Full help includes syntax, parameters, and notes.
Short help only lists domains and commands. A topic can be either a command name such as `query` or a domain name
such as `knowledge`.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `topic` | No | none | Optional command or domain name to inspect. |
| `--short` | No | false | Shows only domains and command names. With a topic, limits the short index to that command or domain. |

#### `init`

**What It Does:** Runs the standard session startup sequence: runtime store migration, memory validation, memory
source registry refresh, log index update, vectorstore update attempt, knowledge graph runtime preparation, and
context hydration.

**Use It When:** Starting a session or resuming after context compaction.

**Result:** Moves legacy stores into the current `database/` layout when safe, imports legacy source-state JSON
into `brain_sources.db`, removes retired derived JSON index files, prints migration warnings for conflicting
non-empty stores, then prints a hydration payload and updates indexes or runtime scaffolding as needed. With
`--verbose-log`, every init phase also reports the specific objects it touches: workspace root, logs DB, memory
source paths, source-registry rows, canonical and legacy log source paths, DB imports, SQLite log index projection,
vector collections, and knowledge repositories.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--limit-diary` | No | 3 | Limits how many recent diary files are included in the hydration payload. |

#### `get-context`

**What It Does:** Builds the context hydration payload without running the entire initialization workflow.

**Use It When:** You need available profiles, diary summaries, change domains, and diagnostics after the workspace
has already been prepared.

**Result:** Prints a structured context summary.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--limit-diary` | No | 3 | Limits how many recent diary files are included. |

#### `check-workspace`

**What It Does:** Validates that memory directories and files follow the expected workspace structure.

**Use It When:** Diagnosing memory layout problems before reading, writing, indexing, or querying memory.

**Result:** Prints a validation report or JSON payload.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--json` | No | false | Emits the validation report as machine-readable JSON. |

#### `create-brain`

**What It Does:** Creates or verifies a local workspace brain script and supporting directories in a target
workspace.

**Use It When:** Preparing another workspace to use the shared brain utilities.

**Result:** Writes workspace-local files under the target workspace and reports created or reused paths.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| workspace_path | No | none | Compact positional target workspace path. |
| `--workspace` | No | none | Explicit target workspace path. |
| `--limit` | No | 10 | Limits how many migrated or inspected paths are printed. |

#### `query`

**What It Does:** Searches the brain through one global consultation point. It can combine knowledge graph index
search, memory vector search, and direct Markdown text matching.

**Use It When:** Asking the brain for information without deciding first which storage backend should answer.

**Result:** Prints grouped terminal matches with logical source headers, source reader commands, fenced content
blocks, entity context, and relation context by default. Human source groups use the shape
`source <diary|memory|log> <title> readed <CLI>`, followed by result rows and a horizontal separator before the
next source. The header exposes only the reader command, for example `read-diary -d 27-06-2026 --time 17:46`,
`read-log -d 04-07-2026 --time 09:10`, `read-profile developer`, or `get-memory-entry "notes.example"`.
Physical paths are hidden unless `--explain` is used. Result body text is printed inside a Markdown fence whose
language comes from the source extension, usually `md` for memory, diary, and logs. Navigation metadata such as
diary/log timestamps, profile names, and source commands belongs to the source header, not to the body block. With
`--deep`, it first parses query context, segments the request into subqueries, retrieves evidence through the
selected backends, ranks keyword/date/entity matches, and prints a contextual answer grounded in those visible
results. Human output orders evidence as matched memory text, semantic fragments, and knowledge relations. JSON
output returns either normalized rows or a deep response object with
query, answer, subqueries, results, and warnings.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| domain | No | all | Optional memory domain filter. If query text is omitted, this positional value is treated as the query text. |
| query | No | none | Query text when a domain was supplied first. |
| `--limit` | No | 5 | Limits matches per selected backend. |
| `--source` | No | all | Selects all, memory, or knowledge sources. |
| `--scope` | No | none | Backward-compatible alias for source selection. |
| `--mechanism` | No | all | Selects all, graph, vector, or direct text retrieval. |
| `--knowledge-scope` | No | all | Selects all, global, or local knowledge graph databases when graph retrieval is enabled. |
| `--deep` | No | false | Enables deep answer mode: parse context, segment query, run subqueries, rank evidence, and synthesize an answer from the retrieved knowledgebase. |
| `--explain` | No | false | Adds source, mechanism, kind, and rank details. Content remains visible without this flag. |
| `--json` | No | false | Emits normalized JSON rows. |

#### `serve-explorer`

**What It Does:** Starts a local stdlib HTTP server for `core/brain_explorer/dist` and exposes JSON API
routes that delegate reads and writes to the live workspace `brain.py` facade.

**Use It When:** You want a visual interface for memory, knowledge, query, profiles, and logs without bypassing
the CLI contracts.

**Result:** Binds the requested host and port, serves static Explorer files, and returns API envelopes shaped as
`{ ok, command, code, data, stdout, stderr, durationMs }` for delegated CLI calls.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--host` | No | `127.0.0.1` | Local HTTP host to bind. |
| `--port` | No | `8127` | Local HTTP port to bind. |
| `--api-timeout` | No | `30.0` | Maximum seconds allowed for one delegated CLI API call. |

## `brain.utilities`

### Commands Index:
Utility commands expose core-owned operational tools through the same consumer
facade as every other Brain capability.

### Command Details:

#### `wiki`

**What It Does:** Delegates documentation checking, generation, or serving to
`core/utilities/documentation_utils/documentation_cli.js`.

**Use It When:** Validating navigable Markdown references or operating a project
documentation wiki without resolving a utility from the global snippets folder.

**Result:** Returns the utility exit code, output, selected mode, and resolved
documentation path. JSON `serve` reports its configuration without starting a
blocking server.

| Parameter | Required | Default | Description |
|---|---|---|---|
| mode | Yes | none | One of `check`, `generate`, or `serve`. |
| documentation_path | Yes | none | Documentation source directory. |
| `--log-domain` | No | inferred | Optional log superdomain for generation. |
| `--host` | No | `127.0.0.1` | Host used by `serve`. |
| `--port` | No | `4173` | Port used by `serve`. |

#### `propagate-agent-prompt`

**What It Does:** Delegates prompt verification or propagation to
`core/utilities/propagate_agent_prompt/propagate_agent_prompt.py`.

**Use It When:** The canonical `<agent_dir>/AGENT.md` contract changes and its
configured mirrors must be checked or synchronized.

**Result:** Compares SHA-256 hashes and reports every destination. Without
`--dry-run`, differing mirrors are copied and verified.

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--source` | No | `<agent_dir>/AGENT.md` | Optional source override. |
| `--mirrors-file` | No | `<core>/database/instruction_mirrors/agent_prompt_mirrors.txt` | Optional mirror-list override. |
| `--dry-run` | No | false | Reports required updates without writing. |

## `brain.application.memory`

### Commands Index:
Memory commands manage editable Markdown memory domains and the memory index.

### Command Details:

#### `memory-structure`

**What It Does:** Lists memory domains, subdomains, and indexed entries in a navigable tree.

**Use It When:** Exploring available memory before reading or writing entries.

**Result:** Prints a tree or JSON path list.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--json` | No | false | Emits machine-readable memory paths. |
| `--uptime-order` | No | false | Sorts tree items by modification time with newest first. |
| `--limit` | No | none | Limits tree items per level. |

#### `add-memory-domain`

**What It Does:** Creates a memory domain or dot-notated subdomain.

**Use It When:** Adding a durable namespace for related Markdown entries.

**Result:** Creates the directory and refreshes the memory index.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| domain | Yes | none | Domain or dot-notated subdomain name. |
| `--json` | No | false | Emits the creation result as JSON. |

#### `set-memory-entry`

**What It Does:** Writes Markdown content to a key inside a memory domain.

**Use It When:** Creating or updating one durable memory entry.

**Result:** Writes the target Markdown file or section and updates the memory index.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| domain | Yes | none | Memory domain or dot-notated subdomain. |
| key | No | none | Entry key when domain.key notation is not used. |
| val | No | none | Markdown content in compact positional form. |
| `--value` | No | none | Alternative explicit content value, useful for scripts. |
| `--json` | No | false | Emits the write result as JSON. |

#### `get-memory-entry`

**What It Does:** Reads a memory entry, domain tree, or full domain text.

**Use It When:** Inspecting source memory directly instead of retrieving through query.

**Result:** Prints entry content, a navigable tree, full text, or JSON depending on flags.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| domain | Yes | none | Memory domain or dot-notated domain.key reference. |
| key | No | none | Entry key when not embedded in the domain argument. |
| `--json` | No | false | Emits content inside a JSON wrapper. |
| `--full-text` | No | false | Prints complete content for files in the domain. |
| `--uptime-order` | No | false | Sorts tree output by modification time. |
| `--limit` | No | none | Limits tree items or printed lines. |

#### `delete-memory-entry`

**What It Does:** Deletes a memory entry or an entire confirmed memory domain.

**Use It When:** Removing obsolete memory from the editable source store.

**Result:** Removes the file or confirmed domain and refreshes indexes.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| domain | Yes | none | Memory domain or subdomain name. |
| key | No | none | Entry key. If omitted, the command targets the whole domain. |
| `--confirm` | No | empty | Must match the domain when deleting a domain recursively. |
| `--json` | No | false | Emits the deletion result as JSON. |

#### `export`

**What It Does:** Exports one memory domain or the whole memory store.

**Use It When:** Creating a copy of memory content for inspection, backup, or transfer.

**Result:** Writes exported content to the requested output directory or prints export information.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| domain | No | all | Memory domain name or all. |
| out_dir | No | none | Compact positional output directory. |
| `--out` | No | none | Explicit output directory. |

#### `update-memory-index`

**What It Does:** Refreshes the SQLite source registry from the Markdown memory tree.

**Use It When:** Manual edits or repairs may have left source mtimes or lightweight source stats stale.

**Result:** Updates `core/database/sources/brain_sources.db` and prints a status report.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--json` | No | false | Emits the rebuild result as JSON. |

## `brain.diary`

### Commands Index:
Diary commands manage chronological human-readable records.

### Command Details:

#### `write-diary`

**What It Does:** Creates or updates a diary entry with a timestamp, title, and body.

**Use It When:** Recording chronological interaction notes or session continuity.

**Result:** Writes the diary entry and refreshes relevant indexes.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| body | No | none | Compact positional diary body. |
| `--datetime` | No | current local time | Explicit entry timestamp. |
| `--title` | Yes | none | Diary entry title. |
| `--text` | No | none | Explicit diary body text. |

#### `read-diary`

**What It Does:** Reads diary entries for a date, optionally narrowed to one exact HH:MM entry.

**Use It When:** Reviewing chronological memory for a session or day.

**Result:** Prints matching diary entries. When `--time` is present, it scans `## DD-MM-YYYY HH:MM[:SS] - Title`
entry headings and returns only the entry whose minute matches the requested 24-hour HH:MM value.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| date | No | current local date | Compact positional date. |
| `--datetime` | No | current local date | Date selector in day-month-year format. |
| `--time` | No | none | Exact entry minute in HH:MM, used by query headers for precise navigation. |
| `--limit` | No | none | Limits printed lines. |

#### `edit-diary`

**What It Does:** Edits an existing diary entry by timestamp.

**Use It When:** Correcting a diary title, replacing body text, or appending a continuation.

**Result:** Rewrites the selected diary entry and preserves the diary file structure.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| timestamp | No | none | Compact positional timestamp identifying the entry. |
| body | No | none | Compact positional replacement or append text. |
| `--datetime` | No | none | Exact timestamp identifying the entry. |
| `--title` | No | unchanged | New diary title. |
| `--text` | No | unchanged | New diary body. |
| `--append` | No | false | Appends text to the existing body. |
| `--replace` | No | none | Text fragment to replace. |
| `--with-text` | No | none | Replacement text used with replace mode. |

## `brain.application.logs`

### Commands Index:
Log commands manage structured technical change history and semantic log retrieval.

### Command Details:

#### `append-log`

**What It Does:** Appends a structured technical log entry with domain, title, type, reason, description, and
impact.

**Use It When:** Recording code, documentation, configuration, or workflow changes.

**Result:** Stores the log entry in `$agent/database/brain_logs.db`, refreshes the SQLite latest-index projection, and prints
``Log entry indexed: `read-log -d <DD-MM-YYYY> --time <HH:MM>` ``.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| compact fields | No | none | Compact positional domain, title, type, why, description, and impact values. |
| `--log-domain` | No | none | Affected package or subdomain. |
| `--title` | No | none | Log title. |
| `--type` | No | none | Change type: feature, fix, refactor, performance, improvement, documentation, or maintenance. |
| `--why` | No | none | Motivation for the change. |
| `--desc` | No | none | Implementation description. |
| `--impact` | No | none | Expected effect of the change. |
| `--datetime` | No | current local time | Explicit log timestamp. |

#### `edit-log`

**What It Does:** Edits an existing workspace log entry by exact timestamp.

**Use It When:** Correcting log metadata or replacing a log description after review.

**Result:** Updates the selected SQLite log row, refreshes the SQLite latest-index projection, and prints
``Log entry indexed: `read-log -d <DD-MM-YYYY> --time <HH:MM>` ``.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| timestamp | No | none | Compact positional timestamp identifying the entry. |
| compact fields | No | none | Compact positional replacement values. |
| `--datetime` | No | none | Exact timestamp identifying the entry. |
| `--log-domain` | No | unchanged | Replacement log domain. |
| `--title` | No | unchanged | Replacement title. |
| `--type` | No | unchanged | Replacement change type. |
| `--why` | No | unchanged | Replacement reason. |
| `--desc` | No | unchanged | Replacement description. |
| `--impact` | No | unchanged | Replacement impact. |

#### `log-index`

**What It Does:** Displays the workspace log index, optionally filtered by a top-level domain.

**Use It When:** Navigating recent technical history by component.

**Result:** Prints indexed log domains and last entries.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| section | No | all | Optional log domain filter. |

#### `update-log-index`

**What It Does:** Imports raw workspace log files into `$agent/database/brain_logs.db`, archives imported originals
under `$agent/.tmp/migrated_logs_db`, rebuilds the latest-entry index, and can import previous `.log` files plus
legacy dated Markdown logs directly into SQLite.

**Use It When:** Log files changed outside the log commands or an index repair is needed.

**Result:** Imports canonical `.log.md` files into SQLite and moves them to `$agent/.tmp/migrated_logs_db`,
refreshes the SQLite `log_index_latest` projection inside `$agent/database/brain_logs.db`, refreshes the local
SQLite source registry at `$agent/database/brain_sources.db`, imports legacy files without generating `.log.md`
intermediates when `--fix` is used, and reports migration or rebuild details. Each index item references its latest
entry with an exact command in the form `read-log -d <DD-MM-YYYY> --time <HH:MM>` so the index remains navigable at
entry granularity. It does not write `$agent/logs/index.md`; use `export-logs --files` or `export-logs --zip` when
Markdown files are needed. If Windows or filesystem cleanup blocks moving an imported raw source, the command prints a
warning, keeps the SQLite import, leaves the original file in place, and exits successfully.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| mode | No | none | Compact positional mode value. |
| `--fix` | No | false | Also imports previous `.log` and legacy dated `.md` logs into SQLite before archiving sources. |

#### `read-log`

**What It Does:** Reads workspace log entries for a specific date, optionally narrowed to one exact HH:MM entry.

**Use It When:** Reviewing technical changes made on a known day.

**Result:** Prints matching log entries from `$agent/database/brain_logs.db`. If the database is empty, the command
imports existing legacy/canonical log files directly into SQLite first. When `--time` is present, it normalizes the
requested minute to 24-hour HH:MM and returns only the matching entry.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| date | No | current date | Compact positional date selector. |
| `--datetime` | No | current date | Date selector. |
| `--time` | No | none | Exact entry minute in HH:MM, used by query headers for precise navigation. |
| `--limit` | No | none | Limits printed entries or lines. |

#### `export-logs`

**What It Does:** Exports DB-backed workspace logs for external consumers.

**Use It When:** Feeding an external consumer through stdout or creating an explicit migration artifact. Persistent
exports are never an internal source of log content.

**Result:** With no target flag, stdout is selected automatically. `--stdout` can still make that choice explicit.
`--files` and `--zip <OUTPUT_PATH>` create migration-only artifacts and emit a warning. Target flags remain
mutually exclusive.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--stdout` | No | default when no target is supplied | Stream Markdown without persistent output. |
| `--domain` | No | all | Domain prefix filter such as `brain.logs`. |
| `--date` | No | none | Exact date filter in DD-MM-YYYY or YYYY-MM-DD. |
| `--time` | No | none | Exact minute filter in HH:MM with optional am/pm. |
| `--from` | No | none | Inclusive lower date/timestamp bound. |
| `--to` | No | none | Inclusive upper date/timestamp bound. |
| `--files` | No | false | Migration only: write canonical `.log.md` export files. |
| `--output` | No | `$agent/logs` | Output directory for `--files`. |
| `--zip` | No | none | Migration only: output zip path for canonical Markdown files. |

#### `query-log`

**What It Does:** Searches workspace logs through the local log vectorstore.

**Use It When:** Looking for prior technical changes by semantic topic.

**Result:** Prints ranked log matches or JSON rows.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| domain | No | all | Optional log domain prefix filter. |
| query | No | none | Semantic query text. |
| `--limit` | No | 5 | Limits semantic matches. |
| `--json` | No | false | Emits log matches as JSON. |

## `brain.application.profiles`

### Commands Index:
Profile commands list and read profile memory bundles.

### Command Details:

#### `list-profiles`

**What It Does:** Lists available agent profiles.

**Use It When:** Choosing the profile to read before specialized work.

**Result:** Prints profile names and the read command hint, or JSON.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--json` | No | false | Emits profile names as JSON. |

#### `read-profile`

**What It Does:** Reads every Markdown entry for one profile.

**Use It When:** Loading complete profile instructions and domain practices.

**Result:** Prints the profile content grouped by entry.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| name | Yes | none | Profile name. |
| `--json` | No | false | Emits profile entries as JSON. |

## `brain.snippets`

### Commands Index:
Snippet commands list and clone reusable utilities.

### Command Details:

#### `list-snippets`

**What It Does:** Lists reusable snippets from the shared home repository, optionally filtered by text.

**Use It When:** Looking for an existing utility before creating a new one.

**Result:** Prints matching snippet names and paths.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| query | No | none | Compact positional filter text. |
| `--filter` | No | none | Explicit filter text. |

#### `clone-snippet`

**What It Does:** Copies a reusable snippet into the current workspace.

**Use It When:** Reusing a shared utility as a workspace-local script.

**Result:** Writes files to the destination directory and reports the copied path.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| name | Yes | none | Snippet name. |
| `--dest` | No | workspace scripts directory | Destination directory relative to the workspace root. |

## `brain.vectorstore`

### Commands Index:
Vectorstore commands maintain embedding-backed indexes and diagnostics.

### Command Details:

#### `update-vectorstore`

**What It Does:** Incrementally updates modified memory files in the shared vectorstore.

**Use It When:** Memory changed and semantic vector retrieval should be refreshed.

**Result:** Adds, updates, or skips vectors and reports recoverable embedding failures when providers are
unavailable. Diary files are chunked at dated entry level; each vector document stores only the entry body as
searchable text and keeps entry title, date, exact HH:MM, source path, and reader command as metadata. This lets
query output show a precise `read-diary -d <date> --time <HH:MM>` command without embedding the timestamp header
as semantic content. Human output prints one `vectorized <source>: entries <N>` line for each changed file and a
final total for entries created and entries deleted.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--json` | No | false | Emits update results as JSON. |

#### `rebuild-vectorstore`

**What It Does:** Resets and rebuilds the shared memory vectorstore from scratch.

**Use It When:** The shared collection is corrupted or intentionally needs a full refresh.

**Result:** Recreates the collection after confirmation and indexes memory documents.
Human output prints one `vectorized <source>: entries <N>` line for each indexed file and a final total for
entries created and entries deleted.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--yes` | No | false | Skips destructive rebuild confirmation. |
| `--json` | No | false | Emits rebuild results as JSON. |

#### `vectorstore-status`

**What It Does:** Displays shared ChromaDB configuration, active models, and vector statistics.

**Use It When:** Diagnosing semantic memory retrieval.

**Result:** Prints vectorstore path, collection, model configuration, and counts.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--json` | No | false | Emits status as JSON. |

#### `rebuild-local-vectorstore`

**What It Does:** Resets and rebuilds a local vector collection.

**Use It When:** Local log retrieval or another local collection needs a destructive refresh.

**Result:** Recreates the selected local collection and indexes supported local records. For the `logs` collection,
each `## DD-MM-YYYY HH:MM am/pm` entry becomes one vector document whose searchable text is the log body and whose
metadata carries the normalized HH:MM time plus `read-log -d <date> --time <HH:MM>`. Human output prints one
`vectorized <log-source>: entries <N>` line per log file and a final total for entries created and entries deleted.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--yes` | No | false | Skips destructive rebuild confirmation. |
| `--collection` | No | logs | Selects the local collection to rebuild. |
| `--json` | No | false | Emits rebuild results as JSON. |

#### `local-vectorstore-status`

**What It Does:** Displays local ChromaDB configuration, collections, and vector statistics.

**Use It When:** Diagnosing local semantic log search.

**Result:** Prints local collection information or JSON.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--json` | No | false | Emits status as JSON. |

## `brain.task-backlog`

### Commands Index:
Task commands manage the workspace backlog stored in the local logs SQLite database. On `init` and `show-backlog`, legacy `$agent/data/backlog.md` task IDs are imported idempotently; persisted SQLite records remain authoritative after import.

### Command Details:

#### `show-backlog`

**What It Does:** Displays the task backlog tree.

**Use It When:** Reviewing pending work by domain.

**Result:** Prints the backlog tree, optionally filtered by domain.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| task_domain | No | all | Optional backlog domain filter. |

#### `add-task`

**What It Does:** Adds a task under a backlog domain.

**Use It When:** Capturing work that should be resumed later.

**Result:** Writes the task to the local logs database and prints the new task identifier.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| task_domain | Yes | none | Backlog domain path. |
| title_pos | No | none | Compact positional title. |
| description_pos | No | none | Compact positional description. |
| `--title` | No | none | Explicit task title. |
| `--description` | No | none | Explicit task description. |
| `--priority` | No | LOW | Task priority level. |

#### `task-finished`

**What It Does:** Marks a workspace task as completed.

**Use It When:** Closing a backlog item after the work is done.

**Result:** Sets the task state to `DONE` in the local logs database.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| task_id | Yes | none | Task identifier, with or without the leading letter. |

#### `set-task-status`

**What It Does:** Sets a task explicitly to `WORKING` or `DONE`.

**Use It When:** Reopening completed work or recording completion without relying on the compatibility alias.

**Result:** Persists the state in the logs database. `DONE` records a completion timestamp; `WORKING` clears it.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| task_id | Yes | none | Task identifier, with or without the leading letter. |
| status | Yes | none | `WORKING` or `DONE`. |

#### `edit-task`

**What It Does:** Changes selected task fields without resetting its persisted state.

**Use It When:** Correcting task text or priority from the Explorer facade or CLI.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| task_id | Yes | none | Task identifier, with or without the leading letter. |
| `--title` | No | unchanged | Replacement title. |
| `--description` | No | unchanged | Replacement description. |
| `--priority` | No | unchanged | Replacement priority: `HIGH`, `MEDIUM`, or `LOW`. |

#### `delete-task`

**What It Does:** Deletes a completed workspace task.

**Use It When:** Removing a task that should no longer exist.

**Result:** Removes the task from the logs database. `WORKING` tasks are rejected unless `--force` is supplied.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| task_id | Yes | none | Task identifier, with or without the leading letter. |
| `--force` | No | false | Explicitly delete a `WORKING` task. |

## `brain.application.knowledge`

### Commands Index:
Knowledge commands manage the private graph runtime, dream source discovery, KG-only lookup, graph inspection,
export, and cognitive consolidation.

### Command Details:

#### `knowledge-init`

**What It Does:** Initializes the selected private knowledge graph runtime scopes, the shared global config file,
SQLite schemas, graph search tables, and minimal structural ontology.

**Use It When:** Preparing a workspace for knowledge graph operations or verifying runtime readiness.

**Result:** Creates or verifies the ignored runtime directories and databases. The global config remains
`core/configs/brain_configs.json` for every scope. Reset mode recreates selected private databases after explicit
confirmation.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--scope` | No | all | Selects all, global, or local knowledge runtimes. |
| `--reset` | No | false | Deletes the private database and SQLite sidecar files before recreating the schema. |
| `--yes` | No | false | Skips reset confirmation. |
| `--json` | No | false | Emits initialization status as JSON. |

#### `knowledge-status`

**What It Does:** Reports scoped graph runtime configuration, database paths, the shared config path, schema
versions, table counts, and configured model stages.

**Use It When:** Checking readiness before dream, query, or export operations.

**Result:** Prints human-readable status or JSON.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--scope` | No | all | Selects all, global, or local knowledge runtimes. |
| `--json` | No | false | Emits status as JSON. |

#### `knowledge-deltas`

**What It Does:** Reviews persisted knowledge delta proposals stored in one private SQLite runtime and then asks
which applicable rows should be applied.
Human output uses the persisted database ID from the selected scope as the display selector, such as `[48]`.

**Use It When:** Inspecting proposals after a dream run, applying selected accepted deltas, checking why a delta
was not applicable, or auditing which proposals were generated from source evidence.

**Result:** Prints proposal details indexed by persisted delta ID, including every proposed entity, relation,
schema suggestion, error, and warning. The terminal syntax uses semantic labels instead of `key=value`: state,
source, proposal counts, accepted counts, errors, warnings, rationale, entities, relations, and schema suggestions
are grouped by purpose. The metric legend is printed above the rows: Et means entities, Re means relations, Ale
means legacy/manual aliases, and Sch means schema suggestions. Relation endpoints render as `[class:"name"]` when
the pending delta or repository entity catalog can resolve them. Live text values render as quoted blue strings
when `--color` is enabled. Legacy proposals from retired contracts are marked `legacy`, hide their raw payload,
and are not applicable for confirmation. With `--id`, the command narrows the review to one persisted proposal
row. After review, human mode prompts for `y`, `n`, or persisted delta IDs such as `48,52`. `--yes` applies every
applicable pending row in the current review selection. With `--json`, application requires `--yes` so automation
cannot mutate the graph by accident.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--scope` | No | global | Selects the global or local delta table. |
| `--id` | No | none | Filters to one persisted pending delta row by the same database identifier shown as `[id]` in human review output. |
| `--yes` | No | false | Applies every applicable pending row in the current review selection. Required for applying in JSON mode. |
| `--limit` | No | 10 | Limits listed proposal rows. |
| `--status` | No | pending | Filters by pending, applied, rejected, failed, or all. |
| `--json` | No | false | Emits review and application payloads as JSON. Without `--yes`, it does not mutate the graph. |

#### `delete-knowledge-deltas`

**What It Does:** Deletes persisted knowledge delta proposals that should not be applied from one selected scope.
The command can delete explicit delta IDs, legacy proposals from retired contracts, or proposals matching a
lifecycle status.

**Use It When:** Cleaning obsolete proposals after reviewing `knowledge-deltas`, removing legacy payloads that no
longer match the current DTO contract, or clearing rejected deltas from the review queue.

**Result:** Shows the selected deletion candidates using the compact delta renderer, asks for confirmation unless
`--yes` is present, deletes matching rows from `pending_deltas`, and prints the deleted count. With `--all`, the
command selects every row inspected by `--limit` and the optional `--status` filter. JSON mode is safe by default:
it reports the selected IDs unless `--yes` is also present.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| ids | No | none | One or more persisted delta IDs to delete. |
| `--scope` | No | global | Selects the global or local delta table. |
| `--all` | No | false | Selects all inspected deltas, optionally narrowed by `--status` and bounded by `--limit`. |
| `--legacy` | No | false | Selects legacy deltas from retired payload contracts. |
| `--status` | No | none | Selects deltas by lifecycle status, such as pending, failed, rejected, applied, or all. |
| `--limit` | No | 200 | Limits candidate rows inspected when selecting by legacy or status. |
| `--yes` | No | false | Deletes without interactive confirmation after candidate selection. |
| `--json` | No | false | Emits deletion summary JSON. Requires `--yes` to actually delete. |

#### `knowledge-query`

**What It Does:** Searches only the private knowledge graph backend, optionally across both graph scopes.

**Use It When:** Debugging KG graph search, comparing KG-only output with global query results, or writing
tests around graph search.

**Result:** Refreshes scoped SQLite source registries, warns when selected graph scopes have source mtimes newer
than the `knowledge_graph` consumer row in `brain_sources.db`, then prints graph matches or JSON rows annotated
with the producing scope. It remains a
utility command; normal consultation should use the global query command.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| query | Yes | none | Text to search in graph entities and evidence. |
| `--scope` | No | all | Selects all, global, or local graph databases. |
| `--limit` | No | 10 | Limits graph matches. |
| `--hybrid` | No | false | Includes vectorstore memory matches when available. |
| `--explain` | No | false | Shows rank and result kind details. |
| `--json` | No | false | Emits results as JSON. |

#### `knowledge-show`

**What It Does:** Shows one scoped knowledge entity by ID, canonical name, or legacy alias, or lists graph
entities, relations, and class definitions.

**Use It When:** Inspecting one entity, browsing KG objects by kind, or filtering graph records before applying a
more specific query.

**Result:** Prints an entity view, a graph-record listing, a no-argument overview, or the equivalent JSON payload.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| entity | No | none | Entity ID, canonical name, alias, or listing filter when a list flag is present. |
| `--entities` | No | false | Lists knowledge graph entities. |
| `--relations` | No | false | Lists knowledge graph relations as readable triples. |
| `--classes` | No | false | Lists registered entity class definitions. |
| `--filter` | No | none | Filters listed rows by text across names, classes, descriptions, predicates, and sources. |
| `--scope` | No | global | Selects the global or local graph database. |
| `--json` | No | false | Emits the selected view as JSON. |

#### `knowledge-export`

**What It Does:** Exports one or both knowledge graphs as JSON-LD.

**Use It When:** Inspecting graph data with linked-data tooling, creating a backup, or handing graph state to an
external viewer.

**Result:** Prints a JSON-LD document for one scope or an object keyed by scope when exporting all scopes.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--scope` | No | all | Selects all, global, or local graph databases. |
| `--format` | No | jsonld | Selects export format. JSON-LD is currently supported. |
| `--json` | No | false | Keeps output machine-readable. |

#### `dream`

**What It Does:** Runs a proposal-first cognitive consolidation pass over changed sources. The pipeline compares
source mtimes in `brain_sources.db` against the selected graph's `knowledge_graph` consumer rows, reads only changed files, asks configured
LLM stages for structural deltas, validates them, persists pending proposals, prints the
proposed deltas with the persisted delta ID as the selector, and asks which applicable deltas should be applied.

**Use It When:** Evolving the global graph from memory, diary, or profiles, or evolving the local graph from
workspace logs.

**Result:** Refuses to start when the selected scope already has pending deltas. In that case it prints a
`delta-status` block with pending, applicable, legacy, and blocked counts, plus helper commands for applying
selected deltas or deleting unwanted pending deltas. When the buffer is clear, it discovers changed
sources from the SQLite source registry, records a dream run summary, and writes pending delta rows in the selected
scope. In human output mode, if the scoped graph has no entities or relations, valid deltas from the first
population pass are applied automatically after deterministic validation, then rendered for audit without a second
confirmation prompt. Normal human output stays focused on proposal review. When `--verbose-log` is present, human
output also logs the concrete orchestration objects and every LLM stage call in real time: scope, source domain,
discovered source paths, filesystem paths, source types, skipped/deleted/changed sources, DB source IDs, pending
delta IDs, semantic-frame object sizes, class catalog objects, stage start, provenance path, Markdown prompt
template path, model, endpoint, semantic frame size, prompt size, graph-context size, prior delta counts, HTTP
response size, elapsed time, parsed delta counts, full model output, and errors when they occur. It does not print
prompt content. During application, `--verbose-log` also logs delta selection, revalidation, accepted counts,
source IDs, delta IDs, write start, write completion, promotion, and application errors.
Provenance is printed for operator auditability; it is not part of the model's knowledge frame.
Terminal proposal output uses the same semantic renderer as `knowledge-deltas`: status values, procedures,
counts, schema tokens, and warning markers each have pragmatic color roles, while live text values are quoted and
blue. The entity stage proposes specific canonical names and descriptions. The relation stage proposes
`subject_name`, `predicate`, and `object_name`; the local harness resolves exact names to internal endpoint IDs
before validation, so the model never needs numeric relation IDs. In interactive terminal mode, the confirmation
prompt accepts `y` to apply every applicable displayed delta, `n` to apply none, or a comma-separated subset of
displayed delta IDs such as `48,52`. Selected deltas write accepted source-anchored entities, resolved relations,
ontology suggestions, and recurrent graph promotions. JSON mode is read-only, disables empty-graph bootstrap
application, suppresses live LLM console logs to preserve valid JSON, and returns the generated or pending
proposal payloads without prompting. If the configured
LLM stages are disabled, unavailable, or missing credentials, `dream` records the run and warnings but does not
generate heuristic replacement deltas.
With `--scope all`, the command processes global memory domains and local logs in separate scoped passes. With
`--scope global`, it processes shared memory, diary, and profiles. With `--scope local`, it processes workspace
logs. The local logs pass discovers `$agent/database/brain_logs.db` as the authoritative source; if the database is
empty, existing legacy/canonical log files are imported directly into SQLite before discovery, and the LLM receives
the DB export frame rather than raw `.log.md` files. With `--prune`, the
command first prints the current scoped knowledge graph status, requires the exact interactive confirmation
RECREATE, deletes that scope's scoped knowledge database plus SQLite sidecars, recreates the schema, and then runs the normal
proposal pass on the fresh graph. The model configuration still comes from the global config file.

**Arguments & Flags:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `--scope` | No | all | Selects all, global, or local. All runs global and local passes when their source families apply. |
| `--domain` | No | all | Selects all, memory, diary, profiles, or logs source families. |
| `--limit` | No | none | Limits changed sources inspected. |
| `--llm` | No | false | Deprecated compatibility flag; `dream` always uses configured LLM stages when they are available. |
| `--min-confidence` | No | config value | Overrides the validation confidence threshold. |
| `--prune` | No | false | Recreates the private knowledge graph before running dream. Requires interactive confirmation after status output. |
| `--json` | No | false | Emits the dream summary and generated proposal rows as JSON without prompting. |
| `--verbose-log` | No | false | Streams object-level source, orchestration, LLM, and application diagnostics during the proposal pass. |

#### `$agent/logs/index.md`

**What It Does:** Stores an exported human-readable workspace log domain summary when explicitly generated.

**Used By:** Operators or external tools that explicitly request Markdown log files through `export-logs`.

**Contract:** The file is not maintained by `init`, `append-log`, `edit-log`, `log-index`, or `update-log-index`.
It is an export artifact generated from `$agent/database/brain_logs.db`; the authoritative log store and internal
latest-entry index are `$agent/database/brain_logs.db` and its `log_index_latest` table, while source freshness lives
in `$agent/database/brain_sources.db`.

#### `delta-status`

**What It Does:** Summarizes the pending delta buffer that blocks a new dream cycle.

**Used By:** The dream command when pending proposals exist in the selected graph scope.

**Contract:** Reports pending row count, applicable row count, legacy row count, blocked row count, and the
corresponding persisted delta IDs. The helper printed beside the status gives exact operator commands for
reviewing, applying, or deleting pending rows. A new dream cycle should not run until this buffer is cleared by
applying wanted deltas or deleting unwanted deltas.

## Flag Details:

#### `--color`

**What It Does:** Enables ANSI color output for terminal formatting.

**Used By:** Router-level parsing before command-specific argument parsing.

**Contract:** The flag affects presentation only. It is stripped from argv before the subcommand parser runs.

#### `--verbose-log`

**What It Does:** Enables extra diagnostic progress output.

**Used By:** Commands that inspect the parsed verbose setting.

**Contract:** The flag affects logging verbosity only and does not change command results. Normal command output
stays focused on requested results. With the flag, progress logs include object-level details such as source
paths, registry rows, vector collections, database targets, source IDs, and delta IDs where the command can know
them. For `dream`, it is required before the CLI prints source discovery, source reads, source skips/deletions,
source DB IDs, pending delta IDs, LLM stage diagnostics, prompt template paths, HTTP response diagnostics, parsed
model outputs, and stage-level model errors. It does not print prompt content.

#### `--json`

**What It Does:** Requests machine-readable output from commands that support it.

**Used By:** Status, read, query, export, vectorstore, profile, and knowledge commands.

**Contract:** Commands that support the flag print JSON instead of terminal prose; unsupported commands do not
declare it.

#### `--limit`

**What It Does:** Bounds the amount of work or output.

**Used By:** Query, create, read, dream, vectorstore, diary, log, and memory tree commands.

**Contract:** Retrieval commands interpret it as result count. Processing commands interpret it as source or item
count. The command detail table defines the exact behavior.

#### `--limit-diary`

**What It Does:** Bounds diary records included during context hydration.

**Used By:** Initialization and context commands.

**Contract:** A positive integer limits recent diary files in the hydration payload.

#### `--source`

**What It Does:** Selects which source family the global query command may search.

**Used By:** The global query command.

**Contract:** Accepted values are all, memory, and knowledge. Invalid values fail before backend calls.

#### `--scope`

**What It Does:** Selects a compatibility source or a knowledge database scope, depending on the command.

**Used By:** Global query as a backward-compatible source alias, and knowledge commands as a graph database scope
selector.

**Contract:** In global query, it behaves like source selection unless the newer source flag is supplied. In
knowledge commands, accepted values are documented per command. ID-based commands select one physical graph scope
so persisted IDs cannot be confused across databases.

#### `--scope all`

**What It Does:** Selects every compatible knowledge scope for commands that can read or process multiple graphs.

**Used By:** Global query, knowledge status, knowledge export, KG-only query, and dream.

**Contract:** For dream, this runs separate global and local passes when their source families apply. It never
merges graph databases or makes IDs interchangeable across scopes.

#### `--scope global`

**What It Does:** Selects the shared HOME knowledge graph.

**Used By:** Knowledge commands and dream when operating on memory, diary, profiles, or other shared Markdown
memory sources.

**Contract:** Resolves to the global HOME knowledge runtime while still using the shared global configuration
file.

#### `--scope local`

**What It Does:** Selects the workspace-local knowledge graph.

**Used By:** Knowledge commands and dream when operating on repository-local logs.

**Contract:** Resolves to the workspace-local knowledge runtime. Local source discovery uses
`$agent/database/brain_sources.db` and does not read shared HOME memory.

#### `--knowledge-scope`

**What It Does:** Selects which knowledge graph database scope global query reads.

**Used By:** The global query command.

**Contract:** Accepted values are all, global, and local. The selector only affects graph retrieval; memory vector
and direct text mechanisms are independent.

#### `--mechanism`

**What It Does:** Selects the retrieval mechanism for global query.

**Used By:** The global query command.

**Contract:** Accepted values are all, graph, vector, and text. Unsupported source and mechanism combinations return
a warning result instead of pretending to search.

#### `--deep`

**What It Does:** Turns global query into deep answer mode.

**Used By:** The global query command.

**Contract:** The command parses deterministic context from the user text, runs selected retrieval backends,
deduplicates and ranks evidence, then synthesizes an answer from returned knowledgebase content. If a configured
text model is available, it may select entities or draft the answer; otherwise deterministic fallback is used.

#### `--explain`

**What It Does:** Adds rank, kind, source, mechanism, or excerpt details to retrieval output.

**Used By:** Global query and KG-only query.

**Contract:** It changes terminal verbosity only. JSON output already carries structured detail.

#### `--value`

**What It Does:** Supplies memory entry content as an explicit option.

**Used By:** Memory write commands.

**Contract:** It avoids ambiguity when positional content would be difficult to quote in scripts.

#### `--full-text`

**What It Does:** Expands memory read output from tree view to complete file content.

**Used By:** Memory read commands.

**Contract:** It prints source text and should be used intentionally when output may be large.

#### `--uptime-order`

**What It Does:** Sorts memory tree output by modification time.

**Used By:** Memory structure and memory read commands.

**Contract:** Newest entries appear first; persisted memory content is not changed.

#### `--confirm`

**What It Does:** Confirms recursive memory domain deletion.

**Used By:** Memory deletion.

**Contract:** The value must match the targeted domain. Entry deletion does not require this recursive safety
confirmation.

#### `--out`

**What It Does:** Selects a destination directory for memory export.

**Used By:** Memory export.

**Contract:** The destination is used for generated export files when provided.

#### `--datetime`

**What It Does:** Selects or assigns timestamps for diary and log commands.

**Used By:** Diary and log write, read, and edit commands.

**Contract:** Read commands accept date-like selectors. Edit commands require an exact timestamp that identifies
one entry.

#### `--title`

**What It Does:** Sets title text for diary, log, or task records.

**Used By:** Diary write/edit, log append/edit, and backlog add commands.

**Contract:** Title is human-readable record metadata and is used in printed output and indexes.

#### `--text`

**What It Does:** Supplies diary body text.

**Used By:** Diary write and edit commands.

**Contract:** It is separate from the text retrieval mechanism used by global query.

#### `--append`

**What It Does:** Appends new text to an existing diary body.

**Used By:** Diary edit.

**Contract:** The existing body is preserved and the supplied text is added.

#### `--replace`

**What It Does:** Selects text in a diary body that should be replaced.

**Used By:** Diary edit.

**Contract:** It should be paired with replacement text so the edit is precise.

#### `--with-text`

**What It Does:** Supplies replacement text for diary replace mode.

**Used By:** Diary edit.

**Contract:** The flag is meaningful only with replace mode.

#### `--log-domain`

**What It Does:** Sets the technical domain for a workspace log entry.

**Used By:** Log append and edit commands.

**Contract:** The value is stored in the log entry heading and used by the log index.

#### `--domain`

**What It Does:** Selects a domain-like scope for commands that process scoped data.

**Used By:** Dream and log commands through command-specific schemas.

**Contract:** Meaning is command-specific. Knowledge commands use source families; log commands use log domains.

#### `--type`

**What It Does:** Sets the log change type.

**Used By:** Log append and edit commands.

**Contract:** Expected values are operational categories such as feature, fix, refactor, performance,
improvement, and documentation.

#### `--why`

**What It Does:** Stores the reason for a log entry.

**Used By:** Log append and edit commands.

**Contract:** The value should explain why the change was made.

#### `--desc`

**What It Does:** Stores the implementation description for a log entry.

**Used By:** Log append and edit commands.

**Contract:** The value should describe what changed in concrete technical terms.

#### `--impact`

**What It Does:** Stores the expected impact of a log entry.

**Used By:** Log append and edit commands.

**Contract:** The value should explain behavioral, documentation, data, or workflow effects.

#### `--fix`

**What It Does:** Enables repair behavior before rebuilding the log index.

**Used By:** Log index update.

**Contract:** The command may migrate legacy logs before rebuilding the index.

#### `--filter`

**What It Does:** Filters snippet listing output.

**Used By:** Snippet list.

**Contract:** Only matching snippet names or metadata are displayed.

#### `--dest`

**What It Does:** Selects the destination for cloned snippets.

**Used By:** Snippet clone.

**Contract:** Relative values are resolved against the workspace root.

#### `--yes`

**What It Does:** Confirms operations that would otherwise ask for interactive confirmation.

**Used By:** Destructive vectorstore rebuilds, knowledge reset, and knowledge delta deletion.

**Contract:** Use only when the destructive operation was already reviewed.

#### `--workspace`

**What It Does:** Selects the target workspace for brain creation.

**Used By:** Brain creation.

**Contract:** The command prepares files in the target workspace rather than the current one.

#### `--collection`

**What It Does:** Selects a local vector collection.

**Used By:** Local vectorstore rebuild.

**Contract:** Defaults to logs when omitted.

#### `--description`

**What It Does:** Supplies backlog task detail.

**Used By:** Task creation.

**Contract:** The value is stored with the task to make later resumption practical.

#### `--priority`

**What It Does:** Sets task priority.

**Used By:** Task creation.

**Contract:** Accepted values are the command-defined priority labels, with LOW as the default.

#### `--reset`

**What It Does:** Recreates the private knowledge database during initialization.

**Used By:** Knowledge initialization.

**Contract:** The command removes the database and SQLite sidecar files only when reset is selected and
confirmation is satisfied.

#### `--id`

**What It Does:** Selects a specific persisted knowledge delta proposal by database identifier.

**Used By:** Knowledge delta review.

**Contract:** The value must identify an existing `pending_deltas` row. Missing IDs return a nonzero command
status.

#### `--all`

**What It Does:** Selects all inspected records for commands that expose explicit bulk behavior.

**Used By:** Knowledge delta deletion.

**Contract:** For `delete-knowledge-deltas`, the flag selects every candidate returned by the current scope,
status filter, and limit. It does not bypass review. Human mode still renders the candidate deltas and asks for
confirmation unless the confirmation flag is present. JSON mode reports the selected IDs unless confirmation is
also supplied.

#### `--status`

**What It Does:** Filters knowledge delta proposal review or deletion by lifecycle status.

**Used By:** Knowledge delta review and knowledge delta deletion.

**Contract:** Typical values are pending, applied, rejected, failed, and all. The all value disables status
filtering.

#### `--legacy`

**What It Does:** Selects pending knowledge deltas that use retired payload contracts.

**Used By:** Knowledge delta deletion.

**Contract:** Legacy selection is derived from deterministic renderer checks, including retired source-document
entities, retired relation fields, missing source IDs, and deterministic fallback rationale text.

#### `--hybrid`

**What It Does:** Adds vector memory matches to KG-only query output.

**Used By:** Knowledge query utility.

**Contract:** It is utility-specific. Ordinary combined retrieval should use the global query command.

#### `--format`

**What It Does:** Selects the knowledge export format.

**Used By:** Knowledge export.

**Contract:** JSON-LD is the supported format in the current implementation.

#### `--llm`

**What It Does:** Keeps older command invocations compatible after `dream` moved to LLM-only structural proposal
generation.

**Used By:** Dream consolidation.

**Contract:** The flag does not enable a separate mode. `dream` already attempts the configured model stages, and
repository writes still require deterministic validation and interactive delta selection.

#### `--min-confidence`

**What It Does:** Overrides the configured confidence threshold for one dream run.

**Used By:** Dream consolidation.

**Contract:** The override applies to deterministic validation for the current run only.

#### `--prune`

**What It Does:** Recreates the private knowledge graph before a dream proposal run.

**Used By:** Dream consolidation.

**Contract:** The command prints current repository status first and then requires the exact interactive
confirmation RECREATE. JSON mode reports that confirmation is required and does not prune.
