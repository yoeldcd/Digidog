# Documentation Utils

Documentation Utils is an opt-in toolkit for checking, generating, and serving
a static Markdown wiki. Brain consumers reach it through the dedicated `wiki`
command; maintainers may run its standalone Node CLI directly.

## Core policy

Brain Explorer is the canonical documentation server for `core/`. Core
development keeps Markdown sources in version control and does not run
`wiki generate` for its own subcomponents. Generated `documentation/wiki/`
trees are ignored build artifacts.

`generate` remains available for an explicit static export outside that normal
flow. `serve` serves such an export and is not a replacement for Brain
Explorer.

## Consumer CLI

```powershell
py '$agent/scripts/brain.py' wiki check <documentation-path> --json
py '$agent/scripts/brain.py' wiki generate <documentation-path> --log-domain <domain> --json
py '$agent/scripts/brain.py' wiki serve <documentation-path> --host 127.0.0.1 --port 4173
```

## Standalone CLI

```powershell
node core/utilities/documentation_utils/documentation_cli.js check <documentation-path>
node core/utilities/documentation_utils/documentation_cli.js generate <documentation-path> --log-domain <domain>
node core/utilities/documentation_utils/documentation_cli.js serve <documentation-path>
```

| Command | Writes files | Contract |
|---|---:|---|
| `check` | No | Validates explicit code references against Markdown headings. |
| `generate` | Yes | Writes an export under `<documentation-path>/wiki/`. |
| `serve` | No | Serves an existing generated export with strict path handling. |

`<documentation-path>` must exist and must be a directory. `--host` defaults
to `127.0.0.1`; `--port` defaults to `4173`. A port of `0` asks the operating
system for an available port during tests.

## Generated export contract

`generate` owns only these artifacts below `documentation/wiki/`:

- `index.html`: Markdown reader shell.
- `logs.html`: optional generated log view.
- `data/index.json`: page and heading manifest.
- `scripts/` and `styles/`: copied browser runtime assets.

Markdown files remain the source of truth. The browser runtime uses Marked,
Mermaid, and Prism for rendering. Generated output must not be committed.

When an explicit export builds `logs.html`, the utility invokes Brain as
`--no-speak export-logs ...`. The runtime silence flag precedes the command, so
wiki generation never triggers avatar narration.

## Architecture

- `documentation_cli.js` parses and dispatches commands.
- `src/cli/` owns argument parsing.
- `src/models/` defines DTO contracts.
- `src/services/` owns discovery, checking, generation, and strict serving.
- `lib/wiki-runtime/` owns browser-side rendering and navigation.
- `tests/` verifies generation, serving, and safety behavior.

## Safety

The output directory is fixed to `<documentation-path>/wiki/`. The server is
rooted at the supplied documentation directory and rejects path traversal.
