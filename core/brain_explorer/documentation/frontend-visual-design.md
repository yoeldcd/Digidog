# Frontend Visual Design

## Design System & Typography

Brain Explorer is an operational interface, not a landing page. It uses dense layouts, stable split panes, compact
headers, and clear blue affordances.

## Global Colors

| Token | Light | Dark | Purpose |
|---|---|---|---|
| `--primary` | `#1264d8` | `#2f8cff` | Active nav, primary buttons, focus accents. |
| `--accent` | `#00a3ff` | `#38c5ff` | Secondary blue highlights. |
| `--bg` | `#f6f8fb` | `#030712` | Page background. |
| `--surface` | `#ffffff` | `#080d18` | Panels and controls. |

## Component Visual Specs

### `app-header`

**Idle / Default:** Sticky top bar with brand, horizontal navigation, and theme toggle.

**Active:** The selected route uses a filled blue nav button.

**Responsive:** Below 900px, the header stacks naturally and the nav scrolls horizontally.

### `panel`

**Idle / Default:** White or near-black rectangular surfaces with 8px radius and a single border.

**Error:** Destructive actions use the danger color only on explicit delete buttons.

### `memory-layout`

**Idle / Default:** Split pane with memory navigation on the left and Markdown editor on the right.

**Responsive:** Collapses into one column and keeps the editor at a stable usable height.
