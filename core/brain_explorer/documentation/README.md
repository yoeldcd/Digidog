<!-- Author: Yoel David <yoeldcd@gmail.com> | X: https://x.com/SAY6267 -->

# Brain Explorer

## Overview

Brain Explorer is a static Web Components application served by `brain.py serve-explorer`. It gives a visual
workspace for memory, knowledge graph, query, profiles, and logs while keeping `brain.py` as the only source of
truth for reads and writes.

The Pictures route provides a responsive, keyboard-accessible carousel over the canonical `pictures/` tree. Its
first request loads the complete domain structure, the tree search filters that in-memory hierarchy locally by
name, and picture records are loaded and cached only when a domain is selected. It also supports fitted previews,
a thumbnail filmstrip, previous/next controls, metadata inspection, and manual description editing. Global Explorer
search can include Pictures and opens a selected result directly in the carousel.

## Domains Taxonomy

src/
  - application/
  - infrastructure/
  - presentation/
  - styles/

dist/
  - Generated static runtime served by the Brain Explorer server.

documentation/
  - Source documentation for architecture, interfaces, and visual design.

## Getting Started

### Installation

```powershell
cd <agent-dir>\core\brain_explorer
npm.cmd run build
```

### Dev Commands

```powershell
npm.cmd run build
npm.cmd run verify
python .\$agent\scripts\brain.py serve-explorer --port 8127
```

### Pictures workflow

```powershell
py '.\$agent\scripts\brain.py' scan-pictures --json
py '.\$agent\scripts\brain.py' describe-picture <picture-id> "A concise searchable description." --json
py '.\$agent\scripts\brain.py' query "family dinner" --source pictures --json
```

The Explorer serves image bytes through an opaque `picture_id`; it never accepts an arbitrary filesystem path.
The server resolves the canonical SQLite record and confines the resulting file beneath the configured pictures
root before returning it.
