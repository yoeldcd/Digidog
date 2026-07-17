# Pictures tree and image-border design QA

- Source visual truth: `C:/Users/user/AppData/Local/Temp/codex-clipboard-00f0cf31-dd75-4e1d-aeac-243c19f2be50.png` and `C:/Users/user/AppData/Local/Temp/codex-clipboard-52ce6795-524c-454b-8cd1-52f3b51d4344.png`
- Implementation screenshot: `D:/.agents/@Angi/$agent/.tmp/t425-focus-implementation.png`
- Viewport: 1280 × 720
- State: Pictures route; local tree filter `roo`; `root` domain loaded; carousel image focused so its border is visible.

## Full-view comparison evidence

The implementation preserves the existing Explorer shell, sidepanel hierarchy, carousel, inspector, palette, typography, spacing, imagery, and copy. The focused image now carries the cyan outline on its own fitted rectangle; the larger render trigger remains visually transparent.

## Focused-region comparison evidence

- Image: the source showed the cyan border on the oversized render layer. The implementation screenshot shows it following the displayed image edges and rounded corners. Runtime geometry measured the image at 506.65 × 380.22 px inside a 506.67 × 390.67 px trigger, confirming the border belongs to the image rather than the trigger.
- Tree: typing `roo` left only `Todo` and `root` visible. CDP network capture recorded zero requests during the three keystrokes. Selecting `root` then emitted one metadata request to `/api/pictures?domain=root` and hydrated the carousel.

## Findings

No actionable P0, P1, or P2 mismatches remain.

- Fonts and typography: unchanged from the standardized Explorer components.
- Spacing and layout rhythm: unchanged; the fitted image keeps its aspect ratio and available viewport margins.
- Colors and visual tokens: the border uses the existing `--accent` token.
- Image quality and asset fidelity: original picture assets are used without stretching or replacement.
- Copy and content: the initial empty state now explains deferred domain loading; existing labels remain intact.

## Comparison history

- Earlier P1: the border surrounded the entire render layer. Fixed by sizing the image element with intrinsic dimensions plus `max-width`/`max-height` and applying the border to that element.
- Earlier P1: tree search triggered a backend request per edit. Fixed by retaining StructureTree's local filter and removing API loading from its search event.
- Earlier P2: the initial response mixed hierarchy and all records. Fixed with a structure-only initial contract and cached, domain-scoped loads on selection.

## Implementation checklist

- [x] Border follows the visible image.
- [x] Tree filter is local and preserves input focus.
- [x] Full domain structure loads first.
- [x] Picture records load lazily and cache by domain.
- [x] Frontend and backend regression tests pass.

## Follow-up polish

No P3 follow-up is required for this scoped change.

final result: passed

---

# Carousel edge-centering design QA

- Source visual truth: `C:/Users/user/AppData/Local/Temp/codex-clipboard-a46523de-51b8-4db2-bef3-82563c19f2fc.png`
- Runtime route: `http://127.0.0.1:8127/#/pictures`
- Viewport: 1280 × 720
- State: `avatar` domain loaded with four real thumbnail options; first and last selections measured independently.

## Comparison evidence

The source showed the first thumbnail pinned to the left edge because the strip had no scrollable runway before it. The implementation adds equal non-rendered flex slots through `::before` and `::after`, preserving the existing thumbnail visuals and the four-item accessible list.

Runtime geometry confirmed both extremes are centered to sub-pixel precision:

- First selection: center delta `-0.00003 px`, `scrollLeft = 0`.
- Last selection: center delta `-0.00003 px`, `scrollLeft = maxScroll = 318 px`.
- Virtual slot width: `243.33 px` on each side at the tested viewport.
- Accessible option count remained `4`; the slots introduced no fake records, focus targets, or image requests.

## Findings

No actionable P0, P1, P2, or P3 mismatch remains. The selected thumbnail keeps the visual center at both boundaries, and the existing incremental hydration and native option semantics remain unchanged.

## Implementation checklist

- [x] Symmetric virtual slots at both strip ends.
- [x] First thumbnail can remain centered.
- [x] Last thumbnail can remain centered.
- [x] Slots are pointer-inert and absent from the accessibility tree.
- [x] No additional picture DOM nodes, records, or loads.
- [x] Structural tests, TypeScript, production build, and live geometry checks pass.

final result: passed

---

# Logs tree modes and collapsible-card design QA

- Source visual truth: `C:/Users/user/AppData/Local/Temp/codex-clipboard-80a3697e-faa2-4805-9f9d-d6bd00fa6b6b.png` and `C:/Users/user/AppData/Local/Temp/codex-clipboard-af942342-0920-4a67-a9ec-209f53164b23.png`
- Runtime route: `http://127.0.0.1:8127/#/logs`
- Viewport: 1280 × 720
- State: date grouping active; 2026 / Julio / 17 expanded; one log selected; card checked both collapsed and expanded.

## Full-view comparison evidence

The implementation keeps the standardized Explorer sidepanel and tree component, adding two mutually exclusive toolbar actions for domain and date grouping. Runtime inspection confirmed real domain totals and a descending date hierarchy (year, month, day, then time), with the newest 17 July entry at 11:23 pm before earlier entries.

## Focused-region comparison evidence

- Tree: deeply nested date leaves remain contained inside the 340 px sidepanel. The selected leaf measured 203.33 px wide and ended at x=340, so it no longer overlaps the main content.
- Cards: selecting a date leaf produced exactly one native `details.log-entry-card`, closed by default. Its visible summary contained the date/time badge, title, domain, type, and change-type tags. Activating the summary exposed the Why, Description, and Impact sections.
- Interaction: both grouping buttons expose correct pressed state; the tree remains keyboard and pointer operable through the shared StructureTree contract.

## Findings

No actionable P0, P1, or P2 mismatches remain.

- Density: verbose content is hidden until requested, reducing the saturated wall-of-text appearance from the source.
- Hierarchy: dates descend from newest to oldest, while domain grouping retains alphabetical order.
- Consistency: toolbar buttons, tree rows, tokens, radii, borders, typography, and spacing reuse existing Explorer primitives.
- Responsiveness: terminal rows use a bounded three-column grid and truncate titles without widening nested tree containers.

## Implementation checklist

- [x] Toggle between domain and date trees.
- [x] Descending year/month/day/time date order.
- [x] Real domain subtree counts.
- [x] Collapsed-by-default log cards.
- [x] Date/time badge, title, and tags remain in the header.
- [x] Expandable Why, Description, and Impact content.
- [x] TypeScript, structural regression tests, build, and live runtime checks pass.

final result: passed
