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

## Evidence

The final tree is checked by package-structure guards, public import smoke, stale-path scanning, acyclic/cross-toolkit import analysis, compileall, git diff --check, and the focused avatar regression suite. Native draft enrichment additionally has deterministic offscreen coverage for thread isolation, control locking, blink feedback, cancellation, and late-result suppression. This document complements those checks; it is not a substitute for them.