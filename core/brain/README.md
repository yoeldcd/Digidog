# Agent Brain

`brain.py` is an agent's workspace command center. Consumers are generated from
`core/core_cli.py`, load the canonical package from `core/brain`, and retain
workspace-local operational data under their own `$agent/` directory. Core owns
shared configuration, databases, assets, Explorer, and utilities.

Every command accepts `--json` (or `-j`) and emits domain-specific fields such as `tasks`, `entries`, `domains`, `snippets`, `server`, or `daemon`. Human Markdown is never embedded as a generic output field. Commands that fail to provide a semantic payload are rejected, runtime failures emit `ok`, `command`, and `error`, and JSON mode suppresses narration so `stdout` contains exactly one JSON document.

## Quick Start

Run this first in a workspace session:

```powershell
python .\$agent\scripts\brain.py init
```

`init` validates the memory structure rooted at the configured `agent_dir`,
refreshes source registries, attempts vectorstore hydration, and prints the
context payload. If the embedding model is unavailable, initialization still
returns the context that can be assembled without embeddings.

Add `--verbose-log` when you need object-level diagnostics. In verbose mode, `init` reports the concrete memory sources, source-registry rows, log files, DB imports, vector collections, and knowledge repositories it touches.

For context without the init checks:

```powershell
python .\$agent\scripts\brain.py get-context
```

If the embedding step fails, retry only that step with elevated permissions:

```powershell
python .\$agent\scripts\brain.py update-vectorstore
```

## Documentation Map

| Document | Purpose |
|---|---|
| `documentation/brain-architecture.md` | System architecture, data flow, storage roots, and failure behavior. |
| `documentation/brain-command-reference.md` | Every registered command, purpose, use case, parameter, default, behavior, and side effect. |
| `documentation/brain-python-modules.md` | Every Python module, class, helper, model, and maintenance contract. |
| `documentation/brain-models-dto.md` | Core DTOs and persisted data shapes. |

## Storage Layout

| Path | Owner | Purpose |
|---|---|---|
| `core/configs/brain_configs.json` | Core | Shared runtime config and canonical `agent_dir`. |
| `core/configs/brain_mirrors.json` | Core | Registered Brain consumer workspaces. |
| `core/configs/brain_avatar_config.json` | Core | Avatar service and voice configuration. |
| `core/database/knowledge/brain_knowledge.db` | Core | Global knowledge graph database. |
| `core/database/sources/brain_sources.db` | Core | Global source registry and consumer freshness state. |
| `core/database/logs/brain_logs.db` | Core | Reserved core logs database. |
| `core/database/vectorstores/` | Core | Global memory and knowledge vectorstores. |
| `core/database/avatar_storage/` | Core | Avatar service runtime storage. |
| `core/assets/avatar/` | Core | Canonical avatar state images. |
| `<agent_dir>/memory/` | Global agent | Durable memory domains and profile entries. |
| `<agent_dir>/snippets/` | Global agent | Reusable agent-owned snippets. |
| `$agent/database/brain_sources.db` | Workspace brain | Local source registry for workspace logs. |
| `$agent/database/brain_logs.db` | Workspace brain | SQLite store for structured workspace log entries, latest-entry indexes, and backlog tasks. |
| `$agent/database/sources.db` | Workspace brain | Local knowledge graph database. |
| `$agent/database/brain_vectorstore/` | Workspace brain | Local vectorstore, including log embeddings. |
| `$agent/data/backlog.md` | Workspace brain | Legacy backlog source, imported idempotently into `brain_logs.db` by `init` and `show-backlog`. |
| `$agent/logs/` | Workspace brain | Compatibility log index and explicit Markdown exports. |
| `$agent/scripts/brain.py` | Workspace brain | Relocatable launcher generated from `core/core_cli.py`. |
| `$agent/.tmp/` | Workspace brain | Temporary artifacts and atomic write staging. |

## Memory

Memory domains are directories and Markdown entries under `memory/`. Use the CLI for all writes so the source registry and optional vectorstore stay aligned.

```powershell
python .\$agent\scripts\brain.py memory-structure
python .\$agent\scripts\brain.py add-memory-domain notes
python .\$agent\scripts\brain.py set-memory-entry notes.example "Reusable note"
python .\$agent\scripts\brain.py get-memory-entry notes.example
python .\$agent\scripts\brain.py query notes "Reusable note"
```

`memory-structure` renders the registered tree from
`core/database/sources/brain_sources.db`, including directories and Markdown
entries with entry count, size, line count, and update metadata.

## Profiles

Profiles live under `memory/profiles/` but have dedicated commands because they are operational identity inputs.

```powershell
python .\$agent\scripts\brain.py list-profiles
python .\$agent\scripts\brain.py read-profile developer
```

`list-profiles` prints available profile names and a helper showing how to read one. `read-profile <NAME>` compiles all entries in `memory/profiles/<NAME>/` into one response. Legacy single-file profiles are still supported.

## Backlog

The workspace backlog lives in `$agent/database/brain_logs.db` alongside local logs. Existing `$agent/data/backlog.md` files are imported idempotently by `init` and `show-backlog`; after migration SQLite owns task fields and states.

```powershell
python .\$agent\scripts\brain.py add-task dev.db "Update schema" -d "Use standard DTOs" -p HIGH
python .\$agent\scripts\brain.py show-backlog
python .\$agent\scripts\brain.py task-finished t1
python .\$agent\scripts\brain.py set-task-status t1 WORKING
python .\$agent\scripts\brain.py delete-task t1
python .\$agent\scripts\brain.py delete-task t1 --force
```

## Logs

Workspace logs are structured entries stored in `$agent/database/brain_logs.db` and summarized internally by the SQLite `log_index_latest` projection. Legacy `.log`, dated `.md`, and existing `.log.md` files are imported into SQLite; `init` and `update-log-index` archive imported originals under `$agent/.tmp`. Archive failures emit warnings without cancelling the SQLite import, leaving the raw source in place for a later retry. `$agent/logs/index.md` is created only by explicit `export-logs` file/zip exports.

Accepted change types for `append-log`, `edit-log`, and `complete-work` are `feature`, `fix`, `refactor`, `performance`, `improvement`, `documentation`, and `maintenance`.

```powershell
python .\$agent\scripts\brain.py append-log brain.presentation.commands "Change title" documentation "Why" "Description" "Impact"
python .\$agent\scripts\brain.py read-log 02-07-2026
python .\$agent\scripts\brain.py read-log -d 02-07-2026 --time 09:10
python .\$agent\scripts\brain.py log-index brain
python .\$agent\scripts\brain.py update-log-index fix
python .\$agent\scripts\brain.py export-logs --domain brain.logs --from 07-07-2026 --to 07-07-2026
python .\$agent\scripts\brain.py export-logs --zip .\$agent\.tmp\logs.zip
python .\$agent\scripts\brain.py query-log brain "profile commands"
```

Never edit the logs database or generated exports manually unless the CLI is being repaired.
When no export target is supplied, `export-logs` safely defaults to stdout.

## Query

`query` is the global consultation point for memory text, memory vectors, and the knowledge graph.

```powershell
python .\$agent\scripts\brain.py query "What happened on Sunday?"
python .\$agent\scripts\brain.py query "What happened on Sunday?" --deep
python .\$agent\scripts\brain.py query diary "project reflection" --source memory --mechanism vector
```

Human output groups evidence by logical source, not by physical path. Source headers expose only a reader command,
for example ``source diary Project reflection readed `read-diary -d 27-06-2026 --time 17:46` ``. Result bodies are shown
in `md` fences and diary/log vector chunks store only entry body text; timestamps, titles, and reader commands
remain metadata.

For knowledge graph evolution, `dream --verbose-log` streams source discovery, source reads, skipped/deleted
sources, source IDs, pending delta IDs, LLM stage calls, validation counts, and application writes.

## Brain Explorer

`serve-explorer` starts a local visual UI for memory, knowledge, query, profiles, and logs. The browser talks to a
local JSON API hosted once by the agent core. `core/configs/brain_mirrors.json`
lists the agent's consumers; the selected mirror changes only the request's
local `WORKSPACE_ROOT`. Global reads and writes remain owned by the same core.

```powershell
python .\$agent\scripts\brain.py serve-explorer --port 8127
```

The static source lives in `core/brain_explorer/src`, source documentation lives
in `core/brain_explorer/documentation`, and generated runtime files live in
`core/brain_explorer/dist`.

## Core Utilities

Core-owned utilities are exposed through dedicated Brain commands:

```powershell
python .\$agent\scripts\brain.py wiki check core\brain\documentation --json
python .\$agent\scripts\brain.py propagate-agent-prompt --dry-run --json
```

Their implementations live under `core/utilities`; consumers do not resolve
them from `snippets`. Prompt mirror destinations are global Brain data stored
at `core/database/instruction_mirrors/agent_prompt_mirrors.txt`; the canonical
prompt itself remains `<agent_dir>/AGENT.md`.

## Co-located Development Consumer

The agent repository that contains `core/` may also be a registered WoSP. In
that case, `core/` remains global agent state while the sibling `$agent/`
directory remains local consumer state. Its `$agent/scripts/brain.py` launcher
is a normal consumer facade whose relative bootstrap happens to point to
`../../core`; it is not the core factory itself.

## Snippets

Agent-authored reusable utilities that are not part of the Brain runtime are
cloned from the configured agent directory into the local workspace.

```powershell
python .\$agent\scripts\brain.py list-snippets
python .\$agent\scripts\brain.py clone-snippet render_workspace_tree
```

## Retired Legacy Sources

The verified migration retired `snippets/brain`, `snippets/brain_explorer`,
`snippets/core.py`, `snippets/documentation_utils`,
`snippets/propagate_agent_prompt`, the root `database/` container, and the old
`$user` prompt-mirror registry from the current tree. Their tracked revisions
remain recoverable through Git history. Runtime code must not restore
dependencies on those legacy locations.

## Health And Export

```powershell
python .\$agent\scripts\brain.py check-workspace
python .\$agent\scripts\brain.py export notes backup
python .\$agent\scripts\brain.py vectorstore-status
python .\$agent\scripts\brain.py local-vectorstore-status
```

Use `rebuild-vectorstore` and `rebuild-local-vectorstore` only when a full destructive rebuild is intentional.

## Safety

Do not store secrets, API keys, passwords, private tokens, or unnecessary personal data. Brain is for durable operational context, memory, profiles, backlog state, and workspace logs.
