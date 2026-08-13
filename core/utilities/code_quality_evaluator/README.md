# Code quality evaluator

This utility is Core-owned and exposed to consumers through the Brain facade.
It supports portable path arguments and never requires callers to construct request JSON.

The Brain `code-quality` command supports four modes: `check` (deterministic gates),
`format` (in-memory formatter candidates), `evaluate` (deterministic plus configured
semantic review), and `schema` (generated DTO schema snapshots).

## Quick use

From a workspace consumer:

```powershell
py {LOCAL_BRAIN_SCRIPT} code-quality src/module.py --mode check --json
py {LOCAL_BRAIN_SCRIPT} code-quality src/module.py --mode check
py {LOCAL_BRAIN_SCRIPT} code-quality src/module.py --mode format --json
py {LOCAL_BRAIN_SCRIPT} code-quality src/module.py --mode evaluate --json
py {LOCAL_BRAIN_SCRIPT} code-quality --mode schema --schema request --json
```

With `--json`, the facade writes one typed result without hashes or raw process/provider
output. Without `--json`, it renders the same result as readable Markdown. Exit code `0` means `pass`;
`1` means `fail` or `disagree`; `2` means `blocked`, `error`, or invalid input/configuration.

See [the evaluator documentation](documentation/README.md) for request DTOs, configuration,
gates, authorization, and operational boundaries.

## Architecture and public contract

The evaluator is a policy-driven, in-memory pipeline. `AnalyzerDispatcher` runs the six
shared artifact gates, then resolves one registered `BaseLanguageAnalyzer` from the total
registry. The language packages are dedicated and independent:

| Language | Package | Parser boundary | Fixed language gates |
| --- | --- | --- | --- |
| Python | `src/application/checks/languages/python` | `ast` plus token summaries | `PY-SYNTAX`, `PY-ANNOTATIONS`, `PY-DOCSTRINGS`, `PY-IMPORTS`, `PY-NO-ANY`, `PY-VERTICAL-LAYOUT`, `PY-COMPACTNESS` |
| JavaScript | `src/application/checks/languages/javascript` | pinned `@typescript-eslint/typescript-estree` 8.66.0 through `node_parser_runner.py` | `JS-SYNTAX`, `JS-DOCUMENTATION`, `JS-VERTICAL-LAYOUT`, `JS-COMPACTNESS` |
| TypeScript | `src/application/checks/languages/typescript` | pinned `@typescript-eslint/typescript-estree` 8.66.0 through `node_parser_runner.py` | `TS-SYNTAX`, `TS-DOCUMENTATION`, `TS-VERTICAL-LAYOUT`, `TS-COMPACTNESS` |
| JSON | `src/application/checks/languages/json` | standard-library JSON parser | `JSON-SYNTAX`, `JSON-STRUCTURE` |
| Markdown | `src/application/checks/languages/markdown` | markdown-it-py block parser | `MD-SYNTAX`, `MD-STRUCTURE`, `MD-COMPACTNESS` |
| PowerShell | `src/application/checks/languages/powershell` | fixed PowerShell parser process | `PS-SYNTAX`, `PS-DOCUMENTATION`, `PS-VERTICAL-LAYOUT`, `PS-COMPACTNESS` |

Every language analyzer emits its exact fixed gate tuple. Syntax failure is explicit: the
syntax gate is `fail`, and every dependent language gate is `blocked`. Deterministic checks
do not short-circuit; all configured gates run and every matching occurrence is retained up
to `occurrences.max_evidence_per_gate`. Formatter failures are represented as `blocked`
formatter results and never write a candidate to disk.

The Node parser receives source only through standard input (`shell=False`) and uses fixed
absolute executable/package paths. No parser, formatter, or evaluator path discovers config,
creates temporary files, or writes a cache. `check` disables semantic transmission;
`evaluate` may use the configured provider reference; `format` keeps the candidate in memory.

The facade exit contract is stable: `0` means `pass`, `1` means `fail` or `disagree`, and
`2` means `blocked`, `error`, or invalid input/configuration.

## Supported path suffixes

The facade maps `.py` to Python, `.js`, `.mjs`, and `.cjs` to JavaScript, `.ts` and `.tsx`
to TypeScript, `.json` to JSON, `.md` to Markdown, and `.ps1` and `.psm1` to PowerShell.
Callers supply workspace-relative paths; the facade reads the source and synthesizes the
typed in-memory request.

## Production policies

`core/configs/code_evaluator_configs.json` contains one complete immutable policy for each
language. Code-language policies require documentation, nested/private declaration coverage,
vertical separation, anti-compaction, fixed gate cardinality, all-occurrence evidence, and
required semantic review. JSON owns syntax and bounded structural rules. Markdown owns
syntax, block structure, and markup-specific anti-compactness without a prose line-length
limit. PowerShell formatting remains explicitly unavailable and returns `blocked`; no
unsupported formatter is simulated.
