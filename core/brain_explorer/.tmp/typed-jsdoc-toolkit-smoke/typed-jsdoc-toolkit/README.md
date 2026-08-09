# Typed JSDoc Toolkit

Cloneable TypeScript documentation tooling that converts existing JSDoc to canonical multiline form, resolves compiler-owned types with the TypeScript `TypeChecker`, and rejects incomplete or duplicated contracts.

## What It Does

- Converts every existing one-line `/** ... */` comment under the configured TypeScript source root into a multiline block.
- Adds `@type {Type}` to documented property declarations and property signatures.
- Adds missing type expressions to existing `@param` and `@returns` tags.
- Preserves authored descriptions and the first authored parameter or return tag while removing duplicates.
- Audits module, declaration, property, parameter, and callable documentation through the TypeScript parser.
- Rejects one-line JSDoc anywhere in the TypeScript source root.

The toolkit does not invent descriptions or create missing semantic prose. Pair it with a project-owned semantic documentation generator when the audit reports missing JSDoc. This separation keeps compiler-owned type resolution deterministic and prevents an LLM from composing comment syntax.

## Prerequisites

- A TypeScript project with `typescript` installed locally.
- A `tsconfig.json` that includes the source modules to format.
- Node.js with ESM support.

## Clone Into a Workspace

Run from the workspace root containing `$agent/scripts/brain.py`:

```powershell
py '.\$agent\scripts\brain.py' clone-snippet typed-jsdoc-toolkit -d build/typed-jsdoc --json
```

The scripts resolve `typescript` from the consumer workspace, so keep the cloned toolkit beneath that project root.

## Commands

Run from the TypeScript project root:

```powershell
node build/typed-jsdoc/format-typed-jsdoc.mjs --project-root=. --source-root=src --tsconfig=tsconfig.json
node build/typed-jsdoc/audit-typed-jsdoc.mjs --project-root=. --source-root=src
```

All options use `--name=value` form:

| Option | Default | Description |
|---|---:|---|
| `--project-root` | Current working directory | Consumer TypeScript project root. |
| `--source-root` | `src` | TypeScript source directory relative to the project root. |
| `--tsconfig` | `tsconfig.json` | Compiler configuration used by the formatter and `TypeChecker`. |
| `--json` | Disabled | Emit formatter results as JSON. |

## Package Scripts

```json
{
  "scripts": {
    "format:typed-jsdoc": "node build/typed-jsdoc/format-typed-jsdoc.mjs --project-root=. --source-root=src --tsconfig=tsconfig.json",
    "audit:typed-jsdoc": "node build/typed-jsdoc/audit-typed-jsdoc.mjs --project-root=. --source-root=src"
  }
}
```

Add `npm run audit:typed-jsdoc` to the normal verification pipeline. A completed migration requires:

1. The formatter changes the source corpus once.
2. The audit passes with zero violations.
3. A second formatter pass reports zero changed modules.
4. The project's strict typecheck and tests remain green.

## Output Contract

The formatter prints the project root, source root, module count, and changed-module count when `--json` is used. It never writes outside the configured source root. The auditor exits with status `1` and line-addressable diagnostics when a contract is violated.