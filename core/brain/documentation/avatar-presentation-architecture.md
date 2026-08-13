# Avatar presentation architecture

This document records the package responsibilities and dependency direction for the native avatar presentation layer. It is the durable architecture reference for the Qt/Tk vertical reorganization; it does not describe runtime behavior beyond the ownership boundaries needed by maintainers.

## Infrastructure capability split

Avatar and Voice are separate infrastructure capabilities with one deliberate dependency level. `infrastructure/avatar` owns the complete typed avatar configuration document and the avatar window child-process lifecycle. `infrastructure/voice` owns speech synthesis, playback, catalogs, daemon transport, message delivery, narration, and its public service facade.

The dependency direction is one-way: Voice may consume the narrow typed boundaries exported by `avatar.configuration` and `avatar.process`; Avatar infrastructure must never import Voice. The canonical responsibility packages are:

```text
infrastructure/avatar/{configuration,process}
infrastructure/voice/{audio,catalog,contracts,daemon,messaging,narration,service}
```

The capability roots contain package initializers only. Deeper legacy module paths, flat message wrappers, and compatibility shims are prohibited; callers import the canonical responsibility package or the intentional top-level `VoiceService` facade.

## Package ownership

The avatar presentation tree keeps one canonical identity per responsibility:

| Package | Responsibility | Allowed contents |
|---|---|---|
| qt/backlog/annotation | Interactive capture annotation editor and its marks/tools | Annotation canvas, dialog, and value models |
| qt/backlog/application | Presentation-local composition root and backlog event coordination | Window construction and controller orchestration; not a domain layer |
| qt/backlog/contracts | Stable backlog value objects and narrow ports | DTOs, enums, theme tokens, and protocols |
| qt/backlog/presentation | Qt adapters and widgets that render and edit the backlog | Capture adapter, filters, icons, detail, widgets, window, and enrichment runner |
| qt/backlog | Explicit public facade | Package exports only |
| qt/{avatar,bubble,controls,markdown,runtime} | Qt avatar feature identities | Canonical feature implementations and exports |
| tk/{avatar,bubble,controls,quota,runtime} | Tk avatar feature identities | Canonical feature implementations and exports |

The toolkit roots contain only package initializers. Tk and Qt remain separate protected variations; neither backend imports the other.

## Dependency direction

Runtime consumers enter through the backlog facade or a canonical feature package. Within the backlog feature, presentation and application adapters depend on the contracts package; annotation uses the contracts needed for its editor state. Package initializers expose stable symbols without creating a second implementation layer. The application package is a presentation-local composition boundary and must not become a domain service.

The `presentation/task_list.py` module owns complete-snapshot reconciliation, task grouping, local visibility, date sorting, and native row identity. `BacklogWindow` coordinates controller callbacks, filter controls, and page navigation; it does not own row reconciliation. The application and contracts layers provide the complete immutable task snapshot and narrow value-object contracts. No backend, repository, persistence, or production application changes are part of this ownership boundary.

The optional `presentation/enrichment/` package owns the blocking-call isolation boundary for unsaved
add/edit descriptions. `TaskFormDialog` knows only the immutable `TaskEnrichmentDraft`,
`TaskEnrichmentResult`, and `TaskDraftEnrichmentPort`; `application/composition.py` adapts that port to
`brain.application.backlog.enrichment.enrich_backlog_draft` and keeps PNG references in memory as data URLs.
The `EnrichmentRunner` moves one request-owning `QObject` to a dedicated `QThread`, and cancellation is
cooperative: controls are restored immediately, generation identity discards late results, and the thread
is allowed to finish naturally without `QThread.terminate()`.

The annotation package owns `AnnotationDialog` composition and `AnnotationSidebar` fixed-width control sections. The
dialog coordinates sidebar actions with the expanding canvas and owns the bottom-right Save/Cancel window footer.
The sidebar owns annotation tool, configuration, and state presentation without editor-state or window-action policy.

Annotation action icons depend one-way on the native SVG icon registry through the presentation icon adapter; the
adapter does not depend on annotation widgets or canvas state.

## Customizable auxiliary windows and screenshot replies

The Qt avatar treats the Markdown bubble and reply composer as separate detached auxiliary windows. Their position and size are runtime presentation state: a user can customize them for the current avatar placement, while the avatar remains the owner of automatic placement and reset.

### Geometry retention and reset

- The bubble starts at 620 × 180. After manual customization, its horizontal origin, width, and bottom edge remain authoritative while the avatar stays in place. Receiving or recovering a message may change only the transient height required by its content, bounded by the physical viewport and the avatar-free vertical lane. Tail direction and distance never move or resize the bubble. Transparent tail space is reserved only on the side where the tail is painted.
- The composer records a user drag or corner resize in its manual rectangle. Its automatic geometry is screen-safe: it uses an 18-pixel edge margin, clamps to the available screen, respects the chrome minimum (at least 320 × 92), and chooses a lane above or below the bubble with a side fallback. Reopening the same non-terminal target reuses the retained manual rectangle.
- Moving the avatar invokes the auxiliary reset lifecycle. The reset clears the bubble manual placement and manual size, restores the standard bubble height limit and default size, repositions the bubble, computes fresh automatic composer geometry, and clears the composer's manual rectangle. This reset changes geometry only; the source contract preserves content and controller lifecycle.

### Composer action row

The composer action row gives all four actions equal layout stretch and keeps the visible and accessible names explicit:

| Visible label | Accessible name | Behavior |
| --- | --- | --- |
| 📷 SCREENSHOT | SCREENSHOT | Emits the screenshot request signal only; it does not submit a reply or terminalize the target. |
| ✅ YES | YES | Submits the literal "Yes" through DeliveryMode.STEER and ignores editor contents. |
| ❌ NOT | NOT | Submits the literal "No" through DeliveryMode.STEER and ignores editor contents. |
| 💭 ENVIAR | ENVIAR | Submits the current editor text through DeliveryMode.STEER. |

All submit actions share target, live-hold, and non-blank validation. A request that passes validation captures the exact current target, marks the terminal action as pending, disables the action row, and dispatches through the asynchronous reply controller. Further action attempts are ignored until a result arrives. The fast Yes/No actions never read or modify the editor.

### Screenshot capture, annotation, and Clipboard

The screenshot request is handled by a dedicated coordinator rather than by reply delivery. It starts only while the same target is active: the instance identity must match, the composer hold must be live, no hold or terminal action may be pending, and no terminal state may have been recorded. Before capture, the coordinator snapshots the composer text and status. A duplicate request focuses the existing modeless annotation editor instead of capturing again.

The capture boundary obtains a source-resolution pixmap and restores any temporarily hidden Qt windows after the grab. A null or failed capture restores the visible editable composer, leaves the Clipboard unchanged, and sends no reply. On success, the composer is hidden and the injected annotation editor receives the captured pixmap. The editor exposes Cancel and Save; its result_pixmap is the annotated source-resolution image.

Save copies the result through the injected Clipboard boundary, restores the same active composer, sets the status to "✓ Screenshot copied to Clipboard.", and records a hidden attachment marker for the exact active instance. The editor text remains unchanged. Only a later ENVIAR action appends the exact instruction "See the image on the Clipboard" once to the outgoing text; YES and NOT remain literal fast responses without that instruction. Save does not submit a reply, close the target hold, or advance the target lifecycle.

Cancel restores the pre-capture composer text and status while preserving the exact target, live hold, and existing Clipboard contents. Capture, editor, Clipboard, and stale-session failures remain local to the current live target: callbacks from an old editor/session cannot modify a newer composer, and failure recovery leaves the composer editable without submitting a task response.

### Target, lifecycle, and package boundaries

The reply target is an immutable CodexThreadTargetDTO. Its non-blank instance_id is the canonical routing identity; speak_id is only an alias, while thread and session fields remain metadata. The composer considers a target active only when the instance identity matches and the hold is live with no pending hold, pending terminal action, or terminal state. The terminal states are CANCELED, SPEAKED, and RESPONSED. RELEASED is a non-terminal released hold that permits the same target to be reopened.

The Qt reply-window package owns presentation composition, action gating, geometry retention, and screenshot-session coordination. The avatar composition root supplies the concrete screen-capture adapter and annotation-editor factory and closes the coordinator with the avatar lifecycle. The screenshot coordinator receives capture, editor, and Clipboard boundaries; it does not perform task operations or import task, application, store, or storage responsibilities, and it performs no disk writes. Its external data handoff is the Clipboard; reply delivery remains the communication controller/service responsibility. Persistence, history, outbox, and storage schemas are outside this UI contract.

## Reorganization decision

The reorganization is structural and move-only:

- Existing implementation bodies, names, typing, docstrings, and comments remain unchanged.
- The ten flat backlog modules are grouped into application, contracts, and presentation.
- The annotation prefix family remains under annotation.
- Imports and package exports are updated only to preserve the canonical public surface.
- Internal class or function segmentation is intentionally deferred to a separately approved change.

## Python Contract and PEP 257 Documentation Audit (Plan 10)

The package underwent a comprehensive contract and documentation audit covering 85 Python files in `core/brain/src/brain/presentation/avatar`:

- **PEP 257 Compliance:** Every class, constructor, method, and function is documented in English. Dataclasses/schemas feature explicit `Attributes:` sections, and callables contain `Args:` and `Returns:` specifications.
- **Typed Contracts over Anonymous Dicts:** Structural `dict[str, Any]` shapes at application and transport boundaries were refactored into typed DTOs/value objects (e.g. `RenderedMarkdown`, `QtSemanticPalette`, daemon status DTOs) while private UI registries (e.g., button lookup tables) remain internal dictionaries with explicit docstrings.
- **Code Legibility:** Logical blocks (imports, declarations, branches, loops, returns) are separated visually by blank lines, nested logic is minimized, and horizontal statement crowding is eliminated.

## Per-command presentation configuration

`brain_avatar_config.json` may define `commands_show_customization` as a map keyed by the underscore-normalized CLI command name; for example, `query-log` resolves `query_log`. Each entry is validated by the immutable avatar configuration DTO and supports:

| Field | Contract |
|---|---|
| `show_message` | Render the command message in the avatar. |
| `speak_message` | Permit TTS narration before mute-level evaluation. |
| `hiden_on_muted` | Hide the visual projection whenever the effective policy mutes speech. The external spelling is retained intentionally. |
| `level` | `important` remains audible during partial mute; `informative` does not. Total mute suppresses both. |
| `pre_processor` | `<none>` preserves eligible output, `<default>` uses reviewed narration behavior, and custom instructions must contain `{OUTPUT}`. |
| `animation` | `<default>` retains the narration emotion; a configured avatar GIF identity overrides it. |

`silent_commands` has absolute precedence over this map and preserves its implicit `--no-speak` behavior. An explicit `--no-speak` has the same dispatch result. Command stdout and JSON output are never changed by avatar presentation policy.

The immutable `AvatarSpeakRequest` in `infrastructure/voice/contracts` carries presentation, narration, provenance, and mute metadata across the daemon boundary. The daemon normalizes regional language tags to their base key, so Spanish requests resolve only the configured `voices.es` entry. Edge synthesis errors are explicit and never fall back silently to an unrelated local voice.

## Synchronous avatar output lifecycle

This is the canonical lifecycle for an accepted synchronous avatar emission. The daemon owns the message FIFO and the per-message lifecycle; the emitter and composer address one daemon-created identity at a time.

### Identity and terminal state machine

`/speak` creates the message identity as `speakId` before the request enters the FIFO. At every boundary, `speakId` backs the canonical message `instanceId`: they are aliases for the same immutable identity, never separate IDs. The typed client stores that value as `InstanceEnqueueResult.instance_id` and exposes `.speak_id` only as the legacy voice vocabulary.

Each identity has one private lifecycle entry and one terminal event. The first terminal transition wins; later transitions cannot overwrite it or release a different instance's waiter.

| Live phase | Terminal transition | Meaning |
|---|---|---|
| Accepted, queued, or active | `SPEAKED` | Natural presentation/playback close completed without a reply. |
| Accepted or held active | `RESPONSED` | The composer submitted non-empty response text for this exact identity. The response text is retained exactly. |
| Accepted, queued, active, or held | `CANCELED` | Exact cancel/discard, timeout cleanup, STOP, daemon shutdown, or a failed processing path won cancellation. |
| `SPEAKED`, `RESPONSED`, or `CANCELED` | None | Terminal; the identity is immutable and late work is discarded. |

`HELD` is a composer-open acknowledgement, not a terminal state. It means the active session is still live while its natural close is waiting for the composer outcome.

### Blocking emitter contract

`VoiceService(synchronous=True)` uses `VoiceDaemonClient.speak_and_wait`. The emitter first calls `/speak`, captures the returned identity, and then waits only on `/instance/wait` for that exact identity. A waiter's private event is released only by terminalization of its own identity; there is no global active-message wake-up and no cross-wake between emitters. This is the per-emitter wait contract.

The default total wait budget for one synchronous emission is 300 seconds. The `--timeout` CLI option overrides that budget with a finite, non-negative value. The daemon lifecycle registry caps each `/instance/wait` segment at 30 seconds, and the client enforces the same cap while continuing with the same exact identity until the total budget is exhausted. A terminal response is returned immediately when that identity reaches `SPEAKED`, `RESPONSED`, or internal `CANCELED`. If a wait segment expires (`408` or `TIMEOUT`), the client continues while budget remains; after the total budget is exhausted, it calls `/instance/cancel` for that exact identity and returns the resulting `CANCELED` state, or the terminal state that won a concurrent race. `KeyboardInterrupt` also cancels that exact accepted identity before being re-raised. An unaccepted `/speak` request returns no logical instance result.

### FIFO composer hold and close behavior

The daemon is the FIFO authority. The UI may request a hold or terminal action, but it never advances the queue itself.

- Without an open composer hold, a natural close transitions the active identity to `SPEAKED`; the active session closes and the next FIFO item may run.
- `POST /instance/composer-open` can open a hold only for the exact live speaking identity, once, before natural close starts. If natural close reaches the hold, it waits without owning the shared lock. Later FIFO items remain pending behind that head, so an `A → B → C` queue keeps `B` and `C` pending while `A` is held.
- Send posts the exact identity and non-empty text to `/instance/respond`. The first winning transition is `RESPONSED`, the exact response is returned, and the hold is released so the daemon can finish the head and advance FIFO.
- Discard or close posts the exact identity to `/instance/cancel` (the Qt close event follows the same path). The first winning transition is `CANCELED`, the hold is released, and the daemon advances without retargeting another message. A queued non-head cancel removes only that identity and preserves the order of the remaining queue.

Typical outcomes are therefore `speak → wait(id) → SPEAKED` when no composer opens, `speak → composer-open(id) → respond(id, text) → RESPONSED` when sending, and `speak → composer-open(id) → cancel(id) → CANCELED` when discarding.

### Passive metadata boundary

`codexThreadId` and the other Codex, host, session, source, consumer, and presentation fields are passive metadata. They may cross the `/speak` request for provenance, display, and reply context, but they never transport, route, gate, wake, or terminalize an instance. `instanceId` is the sole transport and lifecycle-routing identity; the `threadId` echoed by the CLI is metadata, not a substitute for `speakId`/`instanceId`.

### Current routes and output envelopes

The implemented local HTTP lifecycle routes are:

| Route | Request | Successful result |
|---|---|---|
| `POST /speak` | `AvatarSpeakRequest` wire payload | HTTP `202`: `{"ok": true, "queued": true, "speakId": "<id>"}`. `queued` may be false when no logical emission was accepted. |
| `POST /instance/wait` | `{"instanceId": "<id>", "timeoutSeconds": <seconds>}` | HTTP `200` terminal envelope for that identity. The compatibility keys `speakId` and `timeout` are accepted when they identify the same request. |
| `POST /instance/composer-open` | `{"instanceId": "<id>"}` | HTTP `202`: `{"ok": true, "speakId": "<id>", "held": true}`. It is HTTP `409` with `held: false` when the exact live hold cannot be opened. |
| `POST /instance/respond` | `{"instanceId": "<id>", "response": "<non-empty text>"}` | HTTP `202` `RESPONSED` terminal envelope; exact response text is included. |
| `POST /instance/cancel` | `{"instanceId": "<id>"}` | HTTP `202` `CANCELED` terminal envelope, or HTTP `409` when another terminal state already won. |

An HTTP terminal envelope uses the daemon's current wire spelling:

```json
{"ok": true, "speakId": "speak-example", "state": "SPEAKED"}
{"ok": true, "speakId": "speak-example", "state": "RESPONSED", "response": "exact response"}
{"ok": true, "speakId": "speak-example", "state": "CANCELED"}
```

`/instance/wait` returns HTTP `408` with `{"ok": false, "speakId": "<id>", "state": "TIMEOUT"}` when the bounded wait expires. Malformed identities or payloads are `400`; unknown or no-longer-retained identities are `404`. The typed client accepts `instanceId` or `speakId` in a terminal payload, requires the returned identity to equal the requested identity, and rejects contradictory fields.

The synchronous `speak` CLI returns compact, variable-width JSON after the accepted emission(s) for the invocation reach a terminal state. Public stdout uses these shapes:

```json
{"ok": true, "command": "speak", "state": "SPEAKED"}
{"ok": true, "command": "speak", "state": "RESPONSED", "output": "exact response"}
{"ok": true, "command": "speak", "state": "NOT_REPLY"}
```

`SPEAKED` and `NOT_REPLY` contain only `ok`, `command`, and `state`. `RESPONSED` adds `output`, preserving the exact response text. `NOT_REPLY` is the public CLI spelling for an internal daemon `CANCELED` result; the internal lifecycle table and HTTP envelopes continue to use `CANCELED`. The repeat-last path uses the same compact shape, and public stdout does not expose daemon transport IDs, per-emission arrays, operation labels, response field names, or input/file count metadata. The HTTP examples above are internal transport envelopes, not CLI stdout.

### Scope boundary

This lifecycle documents in-memory daemon coordination and output envelopes only. The DB, outbox, persistence, history storage, and storage schemas are unchanged and outside scope; this section makes no storage redesign or storage contract claim.

## Evidence

The final tree is checked by package-structure guards, public import smoke, stale-path scanning, acyclic/cross-toolkit import analysis, compileall, git diff --check, and the focused avatar regression suite. Native draft enrichment additionally has deterministic offscreen coverage for thread isolation, control locking, blink feedback, cancellation, and late-result suppression. This document complements those checks; it is not a substitute for them.
