# Code quality evaluator documentation

The evaluator is a Core-owned utility exposed through the thin Brain adapter.
Brain owns command parsing and transport of CLI arguments; the evaluator owns its contracts and implementation.

## Contracts and source of truth

Request, result, configuration, and model DTOs are defined in the utility's typed source
under `src/domain` and `src/application`. The `schema` mode generates their JSON schemas
in memory on demand; no duplicated schema files are persisted.

The default evaluator configuration is isolated at `core/configs/code_evaluator_configs.json`.
It declares language/path selection, deterministic gates, formatter commands, semantic
requirements, thresholds, retries, timeouts, and provider references. The Brain facade always uses this isolated configuration and does not couple evaluator behavior to Brain runtime state.

CLI callers pass a source path as a positional argument. The internal request DTO still models
`files`, language, and content for programmatic callers; that DTO/schema contract is not a CLI
JSON-input contract.

## Evaluation modes

- `check` disables semantic policy and runs deterministic gates and commands only.
- `format` runs the configured formatter in memory and returns a candidate without writing files.
- `evaluate` runs deterministic checks and the configured semantic policy.
- `schema` emits one generated DTO schema selected by `--schema` (`request`, `result`,
  `format`, `error`, `config`, or `model`).

Deterministic gates and formatters are configured, bounded, and reproducible.
Formatter output is a candidate payload; applying it remains the caller's responsibility.

Semantic evaluation is an explicit external-transmission boundary. Only `evaluate` may
construct the configured transport. Callers must deliberately provide provider credentials
through environment references such as ``$OPENROUTER_API_KEY``. `check`, `format`, and
`schema` do not transmit source content.

The evaluator does not persist prompts, responses, or source files. It does not create
transient files: requests and formatter candidates remain in memory. With `--json`, stdout
contains one typed JSON result; without it, Brain renders the same projection as Markdown.
Provider and command errors are redacted to stable launcher messages;
detailed secrets, prompts, and responses are never printed.

Status precedence is stable: `pass` maps to exit `0`; `fail` and `disagree` map to
exit `1`; `blocked` and `error` map to exit `2`. A nonzero status from any required
deterministic gate or command is surfaced in the result and controls the process exit code.

## Repository-root examples

The Brain facade reads the path argument and builds the internal request DTO.
These commands do not accept JSON on standard input.

```powershell
py {LOCAL_BRAIN_SCRIPT} code-quality src/module.py --mode check --json
```

```powershell
py {LOCAL_BRAIN_SCRIPT} code-quality src/module.py --mode format --json
```

```powershell
py {LOCAL_BRAIN_SCRIPT} code-quality src/module.py --mode evaluate --json
```

```powershell
py {LOCAL_BRAIN_SCRIPT} code-quality --mode schema --schema request --json
```

## Dedicated language packages and gates

The dispatcher owns one total registry of six `BaseLanguageAnalyzer` implementations.
Each implementation owns parsing and language rules for its package; no language analyzer
imports another language analyzer. The fixed gate declarations are:

* Shared artifact gates: `REQ-01-DIGEST`, `REQ-01-CONTENT`, `REQ-01-PATH`,
  `REQ-01-LINE-LENGTH`, `REQ-01-REQUIRED`, `REQ-01-FORBIDDEN`.
* Python: `PY-SYNTAX`, `PY-ANNOTATIONS`, `PY-DOCSTRINGS`, `PY-IMPORTS`, `PY-NO-ANY`,
  `PY-VERTICAL-LAYOUT`, `PY-COMPACTNESS`.
* JavaScript: `JS-SYNTAX`, `JS-DOCUMENTATION`, `JS-VERTICAL-LAYOUT`, `JS-COMPACTNESS`.
* TypeScript: `TS-SYNTAX`, `TS-DOCUMENTATION`, `TS-VERTICAL-LAYOUT`, `TS-COMPACTNESS`.
* JSON: `JSON-SYNTAX`, `JSON-STRUCTURE`.
* Markdown: `MD-SYNTAX`, `MD-STRUCTURE`.
  `MD-COMPACTNESS` rejects compressed markup block boundaries while preserving normal prose,
  inline emphasis/code, tables, nested lists, HTML, and unlimited prose line length.
* PowerShell: `PS-SYNTAX`, `PS-DOCUMENTATION`, `PS-VERTICAL-LAYOUT`, `PS-COMPACTNESS`.

The JavaScript and TypeScript packages use the pinned
`@typescript-eslint/typescript-estree` 8.66.0 dependency through the fixed Node parser
runner. JavaScript enables ESTree/JSX parsing; TypeScript enables TypeScript/TSX parsing
and retains TypeScript-native node summaries. Python uses `ast`; JSON and Markdown have
their dedicated parsers; PowerShell uses its fixed parser process.

Every gate runs even when an earlier gate fails. Evidence is source-ordered and bounded by
the policy's `occurrences.collect_all` and `max_evidence_per_gate` settings. A syntax failure
returns `fail` for the syntax gate and `blocked` for syntax-dependent gates. A disabled
documentation policy returns an explicit `pass` message. Formatter execution is also
in-memory: unavailable or failed formatters return `blocked` results and no file is changed.

## DTO schemas

The `request` schema contains `files[]` (required, each with safe relative `path`, `language`,
and `content`), optional `requirements[]`, `commands[]`, `artifact_checks[]`,
`formatter_checks[]`, `evaluator_id`, `baseline_paths[]`, and `baseline_digests[]`.
`result` is the public check/evaluate projection: `mode`, aggregate `status`, descriptive
`summary`, ordered `files[]`, non-passing `commands[]`, and optional `semantic`. Each file
contains `path`, `language`, `status`, and only its non-passing gates. A gate contains
`gate_id`, `status`, `message`, and actionable `findings[]` with path, optional line range,
kind, summary, and an occurrence count when equivalent findings are grouped. Semantic output contains `status`, local `evaluator_id`,
`blocks_aggregate`, and every configured criterion with status, required score, rationale,
and optional findings.

`format` describes `mode`, aggregate status/summary, and each file's language, status,
message, and optional in-memory candidate. `error` describes only mode, blocked/error status,
and a redacted actionable summary. Public schemas and outputs never expose evidence hashes,
stdout/stderr contents or digests, credentials, prompts, raw provider responses, or repeated
passing gate detail.
Config contains `default_evaluator_id` and `evaluators[]`; each evaluator
contains language policies, formatters, semantic requirements, thresholds, retries, and
timeouts. Model schema contains `model`, `base_url`, environment-variable `api_key`,
`temperature`, `max_tokens`, and `enabled`.

The JSON and Markdown renderers consume the same immutable presentation DTO. JSON preserves
stable machine fields; Markdown presents a status headline, summary, per-file gates and
findings, commands, semantic criteria, and formatter candidates or blockers. The renderer
changes presentation only; it cannot alter evaluation status or suppress a non-passing result.

## Operational boundaries

Use only the direct path form shown above. The command does not read request JSON from
standard input, does not accept generic fake files, and does not require absolute paths.
The Brain facade resolves `{LOCAL_BRAIN_SCRIPT}`, confines paths to the workspace, and then
constructs the typed in-memory request. The utility does not discover configuration from a
caller directory, persist source, create temporary files, or write caches.

Exit codes are stable: `0` for `pass`, `1` for `fail` or `disagree`, and `2` for `blocked`,
`error`, or invalid input/configuration. Only `evaluate` may transmit source to the explicitly
configured semantic provider; `check`, `format`, and `schema` keep source local.
