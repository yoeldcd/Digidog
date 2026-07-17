<!-- Author: Yoel David <yoeldcd@gmail.com> | X: https://x.com/SAY6267 -->

# Frontend Interfaces & Contracts

### `GET /api/voice/messages`

**What It Does:** Combines the selected consumer's persisted message history
with the daemon's temporary speak state and retained audio metadata.

**Used By:** `MessagesView`.

**Contract:** The response always returns `sessions`, a newest-first list of
durable daily session summaries grouped by date and `chatId`. Supplying
`date` and `chatId` returns the selected session's `history` as
`AvatarMessageRecord` objects. `speaks` and `messages` remain runtime
projections used to attach current status and replayable audio.

### Message session navigation

**What It Does:** `MessagesView` projects session summaries as
year -> month -> day -> session through the shared `StructureTree` web
component and requests only the selected leaf's records.

**Contract:** A session identifier is `{date}::{chatId}`. Empty chat
identifiers use the stable `unassigned` suffix and remain isolated by day.
The view uses the same full-height `structure-layout`, sidepanel, divider,
search, selection, and responsive contracts as Memory, Knowledge, Logs, and
Backlog. The content pane preserves Markdown rendering, copy, replay, and audio
download.

### `POST /api/voice/synthesize`

**What It Does:** Generates and immediately plays audio for one historical
message that has no retained audio.

**Contract:** The browser submits only `messageId`. The server resolves text,
language, emotion, and chat metadata from `$agent/database/messages.db` and
queues the daemon with `historical-message-audio:replay`. That internal
operation is intentionally outside the persistence allowlist, so generating
audio never duplicates the historical text record. The response includes the
daemon `speakId`; the view follows that identifier until the retained MP3 is
available, then replaces the generation action with replay and download
controls for the lifetime of the daemon audio store.

### Messages in global search

**What It Does:** The shell exposes Messages as a first-class source and
`QueryView` groups matching rows under the Messages heading.

**Contract:** Explorer sends `source=messages` when it is the only selected
source. Multi-source searches use `source=all` and retain messages returned
through the direct text mechanism.

### Per-project navigation continuity

**What It Does:** Restores the last stable Explorer view independently for each
registered project after the project selector reloads the application.

**Contract:** `AppState` keys the route by normalized project path in browser
local storage. Dashboard, Messages, Memory, Knowledge, Profiles, Logs, Backlog,
Wikis, and Settings are durable routes. Query is intentionally transient and
does not replace the project's last stable view because its submitted query and
result payload are not reload-safe.

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
