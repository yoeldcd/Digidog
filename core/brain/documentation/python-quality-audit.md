# Python quality audit

Date: 2026-07-14

## Scope

The audit covers the 401 Python modules under `src/brain`. It applies the workspace's stored Python and CLI
architecture practices, with emphasis on deterministic runtime behavior, explicit contracts, modularity, and
isolated validation.

## Baseline

| Check | Result |
|---|---:|
| Syntax errors | 0 |
| Bare `except` handlers | 0 |
| Mutable default arguments | 0 |
| Files above 500 lines | 1 |
| Lines above 120 characters | 200 |
| Functions without return annotations | 13 |
| Parameters without annotations | 60 |
| Modules without module docstrings | 7 |

The only oversized module is `infrastructure/voice/daemon.py` at 799 lines. Six missing module docstrings belong
to empty knowledge-package initializers. Most missing parameter annotations are Qt event overrides whose runtime
contract is supplied by PySide6, but they still remain explicit typing debt.

## Priorities

1. Remove runtime dependencies on workspace migration artifacts.
2. Run the complete isolated test suite and repair behavioral regressions before mechanical formatting.
3. Correct high-impact typing, documentation, and line-length defects without changing public contracts.
4. Split the voice daemon only as a dedicated refactor with lifecycle and HTTP regression coverage.

## Remediation results

- Replaced the runtime CSV narration dependency with package-owned declarative contracts.
- Made facade import precedence deterministic when `PYTHONPATH` already contains the Brain source directory.
- Reduced missing module docstrings from 7 to 0.
- Reduced functions without explicit return annotations from 13 to 0.
- Added regression coverage for file-independent narration and facade path precedence.
- Executed 125 isolated test functions successfully after the behavioral changes.

The remaining 200 long lines and the 799-line voice daemon require dedicated formatting and decomposition work.
They are intentionally not rewritten as part of this surgical pass because no project formatter is installed and
the daemon split needs focused lifecycle, concurrency, and HTTP-boundary coverage.
