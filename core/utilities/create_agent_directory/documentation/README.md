<!-- Author: Yoel David <yoeldcd@gmail.com> | X: https://x.com/SAY6267 -->

# Create Agent Directory

`create_agent_directory.py` is the minimal root launcher. All implementation code lives under `src/`; the launcher only delegates into the modular application. It creates `@<agent-name>/`, clones the versioned Brain core, writes
generic configuration, creates empty stores, renders a generic `core/AGENTS.md`, and
adds an initial co-located consumer. Every seed also receives a rendered root
Digidog `README.md` and the canonical GNU AGPL v3 `LICENSE`.

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

The update-agent command takes its source exclusively from the agent root that
owns the invoked core. It synchronizes the injected ordered `tuple[ChangeOperationDTO, ...]` into the target agent. Operations use `COPY`, `REPLACE`, `MERGE`, `RENDER`, and `EXCLUDE`; each contiguous `EXCLUDE` block must be an immediate child of its preceding directory `COPY`. It also refreshes the root README and canonical LICENSE, then regenerates the
target core/AGENTS.md from the public utility template by substituting only the
target agent and user names. It never clones the source core/AGENTS.md.
Identical files are not rewritten; stale files are removed only inside those
explicitly owned code roots and the two public profile roots:
memory/profiles/developer and memory/profiles/worker. Configuration templates are merged on a missing-key-only basis: the target value wins, and live source configuration files are never read. Databases and unrelated memory remain outside synchronization.
Transient trees (`node_modules`, Python/tool caches, nested `.git`, and
generated `documentation/wiki`) are excluded on both sides. They are neither
copied nor removed. Synchronizing a core onto itself is rejected.

## Created layout ~ Source

```text
@agent-name/
|-- LICENSE                  # copied RAW from `@origin\core\utilities\create_agent_directory\files\LICENSE`
|-- README.md                # copied RAW from `@origin\core\README.md`
|-- AGENTS.md                # rendered automatically by `@target\$agents\scripts\brain.py init`
|-- core/
|   |-- AGENTS.md            # partially rendered from template `@origin\core\utilities\create_agent_directory\templates\AGENTS.md`
|   |-- requirements.txt     # copied RAW from `@origin\core\requirements.txt`
|   |-- brain/               # copied RAW from `@origin\core\brain`
|   |-- brain_explorer/      # copied RAW from `@origin\core\brain_explorer`
|   |-- utilities/           # copied RAW from `@origin\core\utilities`
|   |-- configs/             # generated automatically by `@target\core\core_cli.py`
|   |-- database/            # generated automatically by `@target\core\core_cli.py`
|   `-- assets/avatar/       # Versioned avatar state images
|-- $agent/                  # generated automatically by `@target\core\core_cli.py`
|   |-- scripts/brain.py     # generated automatically by `@target\core\core_cli.py`
|   |-- database/            # generated automatically by `@target\core\core_cli.py`
|   |-- logs/                # generated automatically by `@target\core\core_cli.py`
|   |-- data/                # generated automatically by `@target\core\core_cli.py`
|   `-- .tmp/                # generated automatically by `@target\core\core_cli.py`
|-- memory/
|   |-- profiles             # rendered automatically by `@target\$agents\scripts\brain.py init`
|   |   |-- developer        # copied from `@origin\memory\profiles\developer`
|   |   |-- worker           # copied from `@origin\memory\profiles\developer`
|   `-- diary/               # rendered automatically by `@target\$agents\scripts\brain.py init`
|-- snippets/                # rendered automatically by `@target\$agents\scripts\brain.py init`
|-- skills/                  # rendered automatically by `@target\$agents\scripts\brain.py init`
|-- workflows/               # rendered automatically by `@target\$agents\scripts\brain.py init`
|-- pictures/                # rendered automatically by `@target\$agents\scripts\brain.py init`
|-- $workspaces/             # rendered automatically by `@target\$agents\scripts\brain.py init`
|-- $user/                   # rendered automatically by `@target\$agents\scripts\brain.py init`
`-- .tmp/                    # rendered automatically by `@target\$agents\scripts\brain.py init`

```

The initial `$agent/scripts/brain.py` points relatively to the new sibling
`core/` and makes the agent root immediately usable as its first WoSP.

The root `README.md` is copied verbatim from `core/README.md`, the project's
only README source. The root `LICENSE` is copied from `core/utilities/create_agent_directory/files/LICENSE` and contains the complete GNU Affero General Public License v3 text, identified as `AGPL-3.0-only`. This strong copyleft license includes the remote-network source
offer condition appropriate to Brain Explorer and avatar services. Their paths
are returned as `readme_path` and `license_path` in creation JSON output. Both
files are canonical and overwriteable: a later `update-agent` atomically
refreshes changed content and reports them through `updated_files`. The factory
validates that this one README contains the Digidog contract and complete public
screen inventory before creating a clone. Its root-publication paths use
`core/assets/`, so the verbatim root copy resolves images and links.

## Seed policy

The factory copies versioned runtime code and documentation. It never copies:

- live core configuration;
- knowledge, source, log, vector, or avatar databases;
- registered consumers or prompt mirror destinations;
- personal portraits, memory, snippets, skills, or pictures;
- `node_modules`, Python caches, test caches, or generated wiki trees.

`brain_configs.json` receives runtime defaults, `agent_name`, `user_name`, and
the absolute `agent_dir`. Its `pictures` section is a generic schema mockup:
empty `tags` and `characters` guidance, common image extensions, and a disabled
OpenAI-compatible image-model placeholder that references `$VISION_API_KEY`.
It never copies live recognition guidance, identities, provider credentials, or
model choices. Global Codex configuration is not part of the Brain contract.
`brain_mirrors.json` contains only the new co-located consumer.
`brain_avatar_config.json` uses generic local voice defaults and a stable
per-agent loopback port derived from the new agent path. All fixed store
directories exist but contain no records.

Versioned presentation files named `avatar_<state>.gif` and their local
`README.md` contract are copied from the seed's `core/assets/avatar/`. They are
required runtime UI assets, not avatar-storage records. Other portraits or
arbitrary personal files remain excluded.

Versioned `core/assets/screens/` images, including Explorer layouts and the
native avatar view, are copied during creation and updated
with `core/brain`, `core/brain_explorer`, and the root README. This narrow asset
scope keeps every documented Explorer layout renderable without synchronizing
private avatar images or agent-authored pictures.

`update-agent` treats `brain` and `brain_explorer` as the required legacy core
boundary. New versioned roots such as `assets/screens` may be absent from an
older agent; the updater creates them before synchronization instead of
rejecting the migration.

Every clone also receives `core/requirements.txt`, the canonical Python
installation entrypoint. It delegates to `brain/requirements.txt`, keeping the
runtime dependency versions owned by the Brain subsystem while supporting
`py -m pip install -r core/requirements.txt` from the agent root.

The source agent's live memory/profiles/developer and memory/profiles/worker
directories are installed before the receiving Brain bootstrap and synchronized
before update-agent runs init. They remain live operational memory rather than
factory templates. All other memory, including diary, relationships, and
agent-defined domains, stays owned by the receiving agent and is never copied
or removed by this utility. The user and temporary roots are initialized as
empty agent-level domains.
The sole generic template [`AGENTS.md`](../templates/AGENTS.md) deliberately contains no family,
romantic, physical, or existing identity association. It receives only the new
agent and user names. Apart from those identity and relationship removals, it
preserves the canonical environment initialization, response workflows, task
planning methodology, execution guidelines, backlog/memory contracts,
exception handling, and completion report structure.

The source core's `AGENTS.md` & `core/AGENTS.md` template is explicitly
excluded from clone copying. The factory renders the generic template with
the new identity directly into `<new-agent>/core/AGENTS.md`; it does not
create a root instruction mirror. The cloned propagator owns subsequent
localization into consumer roots and
generic mirrors.

## Consumer lifecycle

Creating an agent directory publishes the complete seed and then invokes
`create-brain` through the clone's own `core/core_cli.py`, with the new agent
root as its first consumer workspace. This ensures the consumer structure,
launcher, databases, policies, and project registration follow the canonical
Brain bootstrap instead of a factory-local approximation. A failed bootstrap
rolls back only the newly published agent directory.

Updating an agent synchronizes its governed code and publication files, then
invokes `init --json` through the existing `$agent/scripts/brain.py` consumer.
An update therefore leaves runtime stores and indexes initialized against the
new code, and fails explicitly when the consumer launcher is absent.

## First run

```powershell
py '<new-agent>/$agent/scripts/brain.py' wakeup --json
py '<new-agent>/$agent/scripts/brain.py' serve-explorer --json
```

Creation already runs the consumer's `create-brain` bootstrap, and every
`update-agent` runs its `init` lifecycle. A first interactive `wakeup` therefore
starts from the initialized stores and indexes produced by those operations.
