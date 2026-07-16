<!-- Author: Yoel David <yoeldcd@gmail.com> | X: https://x.com/SAY6267 -->

# Brain Explorer

## Overview

Brain Explorer is a static Web Components application served by `brain.py serve-explorer`. It gives a visual
workspace for memory, knowledge graph, query, profiles, and logs while keeping `brain.py` as the only source of
truth for reads and writes.

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
