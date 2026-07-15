# Avatar state GIF assets

This directory owns the versioned presentation images used by this agent's
avatar window. Runtime avatar-storage records live elsewhere under
`core/database/avatar_storage/`.

## Naming contract

Every state image must use this exact form:

```text
avatar_<state>.gif
```

`<state>` is lowercase and may contain ASCII letters, digits, `_`, or `-`.
The runtime currently resolves GIF files only; `.png`, `.webp`, differently
cased names, and arbitrary portraits are not state assets.

Examples:

| Filename | Runtime use |
|---|---|
| `avatar_awaiting.gif` | Idle, thinking, muted, and awaiting states. |
| `avatar_working.gif` | Explicit background or task work. |
| `avatar_speaking.gif` | Default speech animation and final fallback. |
| `avatar_reacting.gif` | Interactive reaction speech. |
| `avatar_tired.gif` | Awaiting animation when five-hour quota usage reaches 90%. |
| `avatar_sad.gif` | Awaiting animation when weekly quota usage reaches 90%. |
| `avatar_angry.gif` | Optional explicit `angry` speech emotion. |
| `avatar_relax.gif` | Optional custom or legacy `relax` state. |

Speech emotions are extensible. For example, `--emotion happy` first requests
`avatar_happy.gif`; when it is absent, the avatar uses the speech fallback.

## Resolution and fallback

For a requested state, the window:

1. sanitizes the state to `[a-z0-9_-]+`;
2. reads `avatar_<state>.gif` from this directory;
3. if it is missing, reads the caller's fallback state (normally
   `avatar_speaking.gif` or `avatar_awaiting.gif`);
4. finally resolves `avatar_speaking.gif` as the mandatory last fallback.

At minimum, a usable avatar should provide `avatar_speaking.gif` and
`avatar_awaiting.gif`. `avatar_working.gif` is strongly recommended.

The window begins at a 270 x 360 layout and scales the animation while
preserving its aspect ratio. Use a transparent GIF background; the runtime's
synthetic chroma key is `#00ff01` so dark artwork is not accidentally removed.

## Agent seed policy

`create_agent_directory create-agent` copies this `README.md` and every
versioned `avatar_<state>.gif` into a new core. It excludes arbitrary portraits
and runtime avatar storage. `update-agent` deliberately remains limited to
`brain/` and `brain_explorer/`, so avatar identity assets in an existing agent
are never overwritten by a code update.
