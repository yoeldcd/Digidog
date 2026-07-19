<!-- Author: Yoel David <yoeldcd@gmail.com> | X: https://x.com/SAY6267 -->

# Brain Subsystem

## Index:
- [Overview](#overview)
- [Domains Taxonomy](#domains-taxonomy)
- [Getting Started](#getting-started)
- [Subsystem References](#subsystem-references)

## Overview:
The Brain Subsystem is the local command and memory runtime used by the agent workspace. It manages editable
Markdown memories, diary entries, technical logs, backlog tasks, reusable snippets, vector indexes, and a private
knowledge graph. The subsystem is local-first: authored records stay readable on disk, while indexes and databases
support retrieval, consolidation, and operational checks around those records.

The knowledge graph has two isolated SQLite runtimes. The global graph lives under
`core/database/knowledge/brain_knowledge.db` and stores cross-workspace memory, diary, and profile knowledge. The local graph
lives under `$agent/database/sources.db` and stores repository-local knowledge such as workspace logs. Both graphs
use `core/configs/brain_configs.json` for memory/vector settings, model stages, confidence
thresholds, endpoint settings, and secret environment references. This keeps cognition configurable in one place
while letting global and local knowledge be queried together or isolated by scope.

The current retrieval contract has one primary consultation command. The global query flow combines knowledge graph
index search, memory vector search, and direct Markdown text matching behind a single interface. Specialized
knowledge commands remain available for initialization, inspection, export, and maintenance, but ordinary lookup
starts from the global query path. Before query or dream performs heavier work, the source diff layer refreshes
the scoped SQLite source registries from filesystem mtimes. Global source freshness lives in
`core/database/sources/brain_sources.db`; local workspace freshness lives in `$agent/database/brain_sources.db`. The
registry stores source path, source type, title, mtime, size, line count, entry count, active state, and
per-consumer processed mtimes, so query can warn and dream can process only changed sources from one durable
registry contract.

The cognitive knowledge graph is open-world over a stable classifier spine. Entity classes use spaCy base labels
and discovered subtypes such as `ORG.SoftwareProject`; each discovered subtype is also represented by a `CLS`
entity whose `canonical_name` is the PascalCase subtype name, such as SoftwareProject. The `entity_classes`
table materializes those `CLS` entities as a fast classifier cache for validation and future prompts. The `dream`
pipeline uses configured external LLM stages to propose specific entity labels and name-to-name relation
proposals. Within one dream cycle, accepted `CLS` entities are cached immediately so later changed sources can
reuse newly declared classifiers even before the run finishes. The local harness resolves exact entity names to
internal IDs, while deterministic validation and repository rules decide what can become durable state. In human
CLI mode, when a scoped knowledge graph has no entities or relations yet, `dream` treats the run as a
first-population bootstrap and applies valid deltas automatically after deterministic validation.
Knowledge SQLite `sources` rows are identity anchors only: source type, path, title, and active state. File mtimes
and processed timestamps live in `brain_sources.db`, which is shared by source consumers instead of being embedded
in the graph database or duplicated in separate source-state files.

## Domains Taxonomy:

```text
core/brain/
|-- documentation/
|-- README.md
`-- src/
    |-- brain/
    |   |-- cli.py
    |   |-- config.py
    |   |-- application/
    |   |   |-- backlog/
    |   |   |-- knowledge/
    |   |   |-- logs/
    |   |   |-- memory/
    |   |   |-- profiles/
    |   |   `-- querying/
    |   |-- infrastructure/
    |   |   |-- prompts/
    |   |   |-- runtime/
    |   |   |-- sources/
    |   |   `-- vectorstores/
    |   |-- presentation/
    |   |   |-- actions/
    |   |   |-- commands/
    |   |   |-- parser/
    |   |   |-- router/
    |   |   |-- views/
    |   |   `-- terminal.py
    `-- tests/
```

The source tree now uses a Python `src` layout. Importable package code lives under `core/brain/src/brain`,
tests live under `core/brain/src/tests`, and durable documentation remains under `core/brain/documentation`.
`brain.config` contains constants only. Runtime path behavior lives in `brain.infrastructure.runtime.paths`,
knowledge config loading and repair live in `brain.application.knowledge.runtime.config_store`, knowledge scope
selection lives in `brain.application.knowledge.runtime.scopes`, and vectorstore settings/recovery behavior lives
under `brain.infrastructure.vectorstores`. CLI command modules are declarative metadata only; executable command
logic lives in `brain.presentation.actions`, parser construction lives in `brain.presentation.parser`, routing
lives in `brain.presentation.router`, and human query rendering lives in `brain.presentation.views.query`.

## Subsystem References:

- [Picture intelligence and img2text](brain-pictures-interfaces.md)
- [Brain interfaces and contracts](brain-interfaces.md)
- [Brain models and DTOs](brain-models-dto.md)
- [Brain CLI commands](brain-cli-commands.md)
- [Brain security](brain-security.md)

## Getting Started:

### Installation:

```bash
set PYTHONPATH=core/brain/src
```

The local workspace wrapper normally calls the same package through the workspace brain script:

```bash
py ".\$agent\scripts\brain.py" init
```

### Dev Commands:

```bash
python -m brain.cli help --short
python -m brain.cli help knowledge --short
python -m brain.cli init
python -m brain.cli query "knowledge graph"
python -m brain.cli query "schema evolution" --source knowledge --mechanism graph --knowledge-scope all
python -m brain.cli query profiles "query contract" --source memory --mechanism text
python -m brain.cli knowledge-init
python -m brain.cli knowledge-status --scope all --json
python -m brain.cli dream --scope all --limit 1
python -m brain.cli dream --scope local --domain logs --limit 1
python -m brain.cli knowledge-deltas --scope global --limit 5
python -m brain.cli knowledge-deltas --scope global --id 2
python -m brain.cli knowledge-deltas --scope global --limit 5 --yes
python -m brain.cli delete-knowledge-deltas --scope global --all --limit 20
python -m brain.cli delete-knowledge-deltas --scope local --legacy --yes
python -m brain.cli dream --scope local --domain logs --prune
python -m brain.cli knowledge-export --scope all --json
```

Run the Python test suite after code or contract changes:

```bash
py -m unittest discover core/brain/src/tests
```
