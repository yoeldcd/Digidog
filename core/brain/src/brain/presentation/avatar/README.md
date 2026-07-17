<!-- Author: Yoel David <yoeldcd@gmail.com> | X: https://x.com/SAY6267 -->

# Avatar presentation packages

The avatar presentation is split by ownership instead of toolkit prefixes:

- `window/` owns backend selection, configuration, the executable entrypoint,
  and native window priority.
- `qt/` owns the PySide6 window, painted controls, and Markdown bubble.
- `tk/` owns the Tk fallback window and its animated GIF renderer.
- `interactivity/` owns toolkit-neutral dialogue, emotion, and reaction rules.

Dependency direction is `window -> qt|tk -> interactivity`. Toolkit packages may
read shared window configuration, but neither toolkit imports the other.
## Runtime privilege contract

The voice daemon, avatar window, loopback HTTP endpoint, and audio playback run
with the interactive user's standard token. None of these responsibilities
requires administrator rights. On Windows, the daemon is detached from the
short-lived Brain CLI process with DETACHED_PROCESS,
CREATE_NEW_PROCESS_GROUP, and CREATE_NO_WINDOW; the avatar remains a normal
GUI child owned by that daemon.

Codex sandbox authorization and Windows administrator elevation are separate
concerns. A GUI launched by a CodexSandbox account belongs to the sandbox
desktop and is not visible in the interactive user's session. Brain therefore
refuses cold startup from that account instead of requesting runas or reporting
an invisible process as healthy. Start the service from the interactive user
CLI; once it is running, Codex clients may communicate with its loopback
endpoint without owning the GUI process.

## Markdown presentation contract

The Qt bubble materializes explicit escaped line breaks, separates inline list
markers, and projects unambiguous comma enumerations containing four or more
items as Markdown lists. Fenced and inline code remain byte-for-byte unchanged.

Links use contrast-safe, underlined colors in both supported themes. Select the
theme when starting or reusing the daemon:

```powershell
py '.\$agent\scripts\brain.py' start-avatar-service --mode dark --json
py '.\$agent\scripts\brain.py' start-avatar-service --mode light --json
```

The mode is daemon state, so an already running avatar receives the new theme
through its normal status polling contract.

The detached reply composer inherits the same active theme and exposes only the
currently supported `Enviar` action. Queue and interrupt controls are omitted
until the native host contract can execute those delivery modes.

## Image viewer contract

The Markdown bubble accepts native `<img>` tags, ordinary Markdown images, and
extended Markdown dimensions:

```markdown
![Architecture](https://example.com/architecture.png){width=640 height=360}
<img src="D:/assets/reference.png" width="480" height="320">
```

Sources may be workspace-relative paths, absolute Windows or UNC paths,
`file://` URLs, embedded `data:` images, or HTTP, HTTPS, and FTP URLs.
Dimensions are bounded to 16-1200 pixels per axis. Remote image reads are
limited to 100 MB and accepted only when Qt decodes the payload as an image.
