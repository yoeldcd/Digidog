# Create Agent Directory

`create_agent_directory.py` is a standalone factory for a new agent ownership
boundary. It creates `@<agent-name>/`, clones the versioned Brain core, writes
generic configuration, creates empty stores, renders a generic `AGENT.md`, and
adds an initial co-located consumer.

It is intentionally not callable through Brain. A running Brain operates one
existing agent; creating another agent must remain an explicit external action.

## CLI

```powershell
py core/utilities/create_agent_directory/create_agent_directory.py <parent-path> `
  --agent-name <name> `
  --user-name <user> `
  --json
```

The explicit equivalent is `create-agent <parent-path>`. The legacy invocation
without that command remains supported.

Compatibility aliases `--agent_name` and `--user_name` are accepted. The agent
name may be passed with or without `@`; the destination folder is always
normalized to `@<name>`.

| Argument | Required | Contract |
|---|---:|---|
| `<parent-path>` | Yes | Parent in which the agent folder is created. It may be created if absent. |
| `--agent-name` | Yes | Letters, digits, `_`, and `-`; must begin with a letter or digit. |
| `--user-name` | Yes | Non-empty, single-line collaborator display name. |
| `--json` | No | Emits one machine-readable success or error object. |

The command refuses to overwrite an existing destination. It builds in a
temporary sibling and publishes the completed directory with one rename, so a
failed copy does not expose a partial agent.

### Update an existing clone

```powershell
py core/utilities/create_agent_directory/create_agent_directory.py update-agent `
  <existing-agent-root-or-core> `
  --json
```

`update-agent` takes its source exclusively from the `core/` containing the
invoked utility. It synchronizes only `brain/` and `brain_explorer/` in the
target clone. Files with identical content are not rewritten; changed and new
files are replaced atomically, and destination files absent from the source are
removed. The operation never reads from or writes to target `configs/`,
`database/`, `assets/`, `utilities/`, `AGENT.md`, or agent-authored domains.

Transient trees (`node_modules`, Python/tool caches, nested `.git`, and
generated `documentation/wiki`) are excluded on both sides. They are neither
copied nor removed. Synchronizing a core onto itself is rejected.

## Created layout

```text
@agent-name/
|-- AGENT.md
|-- core/
|   |-- requirements.txt
|   |-- brain/
|   |-- brain_explorer/
|   |-- utilities/
|   |-- configs/
|   |-- database/
|   `-- assets/avatar/       # Versioned avatar state images
|-- $agent/
|   |-- scripts/brain.py
|   |-- database/
|   |-- logs/
|   |-- data/
|   `-- .tmp/
|-- memory/
|   |-- profiles/
|   `-- diary/
|-- snippets/
|-- skills/
|-- workflows/
|-- pictures/
|-- $workspaces/
|-- $user/
`-- .tmp/
```

The initial `$agent/scripts/brain.py` points relatively to the new sibling
`core/` and makes the agent root immediately usable as its first WoSP.

## Seed policy

The factory copies versioned runtime code and documentation. It never copies:

- live core configuration;
- knowledge, source, log, vector, or avatar databases;
- registered consumers or prompt mirror destinations;
- personal portraits, memory, snippets, skills, or pictures;
- `node_modules`, Python caches, test caches, or generated wiki trees.

`brain_configs.json` receives runtime defaults and the new absolute
`agent_dir`. `brain_mirrors.json` contains only the new co-located consumer.
`brain_avatar_config.json` uses generic local voice defaults and a stable
per-agent loopback port derived from the new agent path. All fixed store
directories exist but contain no records.

Versioned presentation files named `avatar_<state>.gif` and their local
`README.md` contract are copied from the seed's `core/assets/avatar/`. They are
required runtime UI assets, not avatar-storage records. Other portraits or
arbitrary personal files remain excluded.

Every clone also receives `core/requirements.txt`, the canonical Python
installation entrypoint. It delegates to `brain/requirements.txt`, keeping the
runtime dependency versions owned by the Brain subsystem while supporting
`py -m pip install -r core/requirements.txt` from the agent root.

`memory/profiles/` and `memory/diary/` are initialized as empty special-memory
domains. `$user/` and `.tmp/` are also created as empty agent-level domains so
the generated instruction and Brain contracts are immediately satisfiable.

The template [`AGENT.md`](../AGENT.md) deliberately contains no family,
romantic, physical, or existing identity association. It receives only the new
agent and user names. Apart from those identity and relationship removals, it
preserves the canonical environment initialization, response workflows, task
planning methodology, execution guidelines, backlog/memory contracts,
exception handling, and completion report structure.

## First run

```powershell
py '<new-agent>/$agent/scripts/brain.py' wakeup --json
py '<new-agent>/$agent/scripts/brain.py' serve-explorer --json
```

The first Brain operation may initialize empty SQLite and vector stores. That
runtime initialization happens after creation, not inside the factory.
