# Frontend Interfaces & Contracts

## Interface Index

```ts
type ThemeMode = "light" | "dark";

interface CliCommandResult {
    ok: boolean;
    command: string[];
    code: number;
    data?: unknown;
    stdout: string;
    stderr: string;
    durationMs: number;
    error?: string;
}
```

## Service Contracts

### `BrainApiClient`

**What It Does:** Converts UI intents into local HTTP requests.

**Used By:** Memory, knowledge, query, profiles, logs, and settings components.

**Contract:** Returns the server envelope unchanged so the UI can expose command, stdout, stderr, and parsed data.

### `AppState`

**What It Does:** Stores active route, theme, and latest CLI command result.

**Used By:** `brain-explorer-app` and `brain-settings-view`.

**Contract:** Emits a `change` event after each route, theme, or raw-result update.

## API Contracts

### `/api/memory/tree`

**What It Does:** Calls `brain.py memory-structure --json`.

**Use It When:** Rendering the memory navigation pane.

**Result:** Returns a `CliCommandResult` whose `data` is a list of dot-notated memory paths.

### `/api/memory/entry`

**What It Does:** Calls `get-memory-entry`, `set-memory-entry`, or `delete-memory-entry`.

**Use It When:** Reading, saving, or deleting Markdown memory entries.

**Result:** Returns the stable CLI envelope with parsed JSON when available.

### `/api/knowledge/*`

**What It Does:** Calls `knowledge-status`, `knowledge-show`, `knowledge-query`, `knowledge-export`, or
`knowledge-deltas`.

**Use It When:** Inspecting graph state, listings, searches, or pending delta proposals.

**Result:** Returns the command envelope and parsed graph payloads.
