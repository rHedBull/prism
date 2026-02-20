# Code Architecture Knowledge Graph — Design Document

**Date:** 2026-02-20
**Scope:** Part 1 — Base Version (Code-Centric)
**Primary use case:** Codebase exploration

---

## Overview

A system that parses codebases (Python + TypeScript/JS), builds a typed property graph of code entities and relationships, and renders an interactive 3D visualization using Three.js. The visualization uses stacked abstraction layers with force-directed node layouts within each layer.

## Architecture

Three components:

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Graph Builder   │────>│  .callgraph/ │────>│  Three.js Web UI │
│  (Python CLI)    │     │  JSON files  │     │  (localhost)      │
└─────────────────┘     └──────────────┘     └──────────────────┘
```

A Claude Code plugin (`/graph` slash command) will be added later for agent-driven semantic enrichment.

---

## 1. Graph Builder (Python CLI)

### Parsing

- Uses `tree-sitter` with Python and TypeScript/JavaScript grammars
- Walks the file tree, parses each source file into AST
- Language detection by file extension

### Node extraction

| Node type | Source |
|-----------|--------|
| Directory / Package | File system |
| Module / File | File system + AST root |
| Class / Struct | AST class definitions |
| Function / Method | AST function definitions |

### Edge extraction

| Edge type | Detection method |
|-----------|-----------------|
| `contains` | Parent-child in file tree or AST |
| `imports` | Import statements in AST |
| `calls` | Function call expressions in AST |
| `inherits_from` | Class base classes in AST |
| `depends_on` | Derived from imports (module-level) |

### Attributes per node

- `id` — unique identifier (e.g., `func:backend/services/auth_service.py:authenticate_user`)
- `type` — directory, file, class, function
- `name` — short name
- `language` — python, typescript, javascript
- `file_path` — relative path from repo root
- `lines_of_code` — LOC count
- `abstraction_level` — integer assigned heuristically by directory convention
- `export_count` — number of public exports (functions, classes)

### Abstraction level assignment

Heuristic based on directory names and import direction:
- Level 0: models, types, schemas (data definitions)
- Level 1: services, utils, hooks (business logic)
- Level 2: api, routes, components (interface layer)
- Level 3: main, app, index (entry points)

Fallback: infer from dependency direction (nodes with no dependents = top, nodes with no dependencies = bottom).

### Output format

Two JSON files in `.callgraph/`:

**nodes.json:**
```json
[
  {
    "id": "file:backend/services/auth_service.py",
    "type": "file",
    "name": "auth_service.py",
    "language": "python",
    "file_path": "backend/services/auth_service.py",
    "lines_of_code": 50,
    "abstraction_level": 1,
    "export_count": 4,
    "parent": "dir:backend/services"
  }
]
```

**edges.json:**
```json
[
  {
    "from": "file:backend/api/auth_routes.py",
    "to": "file:backend/services/auth_service.py",
    "type": "imports",
    "weight": 3
  }
]
```

---

## 2. Three.js Web Visualizer

### Visual model

**Stacked layers** arranged vertically in 3D space:
- Each layer = one abstraction level (derived from `abstraction_level` attribute)
- Layers rendered as translucent rectangular planes
- Vertical spacing between layers proportional to edge density between them

**Within each layer — force-directed layout of 3D blocks:**
- Each node is a `BoxGeometry` sitting on the layer plane
- Block height = `lines_of_code` (normalized)
- Block base size = `export_count` or uniform
- Block color = language (blue tones = Python, green tones = TypeScript)
- Position computed by force-directed algorithm based on intra-layer edges

**Edges:**
- Rendered as bezier curves (`CubicBezierCurve3` → `TubeGeometry` or `Line`)
- Color by type: `imports` = blue, `calls` = orange, `inherits_from` = purple, `depends_on` = gray
- Thickness = `weight` (number of references)
- Cross-layer edges arc vertically between layers
- Intra-layer edges curve horizontally within a layer

### Camera and focus

Two primary view modes:

**Vertical view** (default):
- Camera angled above the stack, looking down
- See all layers, cross-layer edges, overall structure
- Good for understanding abstraction flow

**Horizontal view** (focused on one layer):
- Camera level with a single layer, looking into it
- See the force-directed graph layout within that layer
- Peer relationships and intra-layer topology

Transitions:
- Click a layer → smooth camera animation to horizontal view of that layer
- Click background or press Escape → animate back to vertical view
- OrbitControls for free rotation/zoom at any time

### Semantic zoom

| Distance | Detail level |
|----------|-------------|
| Far | Layers as solid colored planes with text labels |
| Medium | 3D blocks visible on each layer, cross-layer edges shown |
| Close | Function/class names visible on blocks, intra-file edges shown |

### Interaction

- **Hover** a node → info tooltip (name, LOC, type), highlight all connected edges, fade unconnected nodes
- **Click** a node → select it, show detail panel, highlight full dependency chain across layers
- **Click** a layer label → focus that layer (horizontal view)
- **Scroll** → zoom in/out
- **Right-drag** → rotate camera
- **Middle-drag** → pan

### UI elements

- Floating labels on layers (e.g., "models/", "services/", "api/")
- Node info panel (top-right corner) on hover/select
- Minimal controls: reset view button, layer toggle checkboxes
- No sidebar or walkthrough in MVP

---

## 3. Tech Stack

| Component | Technology |
|-----------|-----------|
| Graph builder | Python 3.12+, tree-sitter, tree-sitter-python, tree-sitter-typescript |
| Graph storage | JSON files in `.callgraph/` |
| Web server | Python `http.server` (dev) |
| 3D renderer | Three.js |
| Camera controls | Three.js OrbitControls |
| Animations | tween.js |
| Force layout | d3-force-3d or custom |
| Frontend | Vanilla JS + ES modules (no bundler) |

---

## 4. Test target

The `test-project/` directory in this repo — a full-stack task management app:
- Backend: Python/FastAPI (~280 LOC, 16 files)
- Frontend: TypeScript/React (~340 LOC, 11 files)

---

## 5. MVP scope

### In scope

- Parse Python + TS/JS via tree-sitter
- Extract: directories, files, classes, functions
- Extract: imports, calls, contains, inherits_from
- Compute: LOC, abstraction_level, language
- JSON output to `.callgraph/`
- 3D stacked layer visualization
- Force-directed layout within layers
- 3D blocks with height = LOC
- Color-coded edges by type
- Hover to highlight, click to focus
- Vertical ↔ horizontal camera transitions
- Semantic zoom (3 detail levels)
- OrbitControls for free navigation

### Out of scope

- Claude Code plugin / agent enrichment
- Walkthrough / narrative panel
- Time dimension (git history)
- Runtime metrics overlay (profiling, tracing)
- Advanced queries
- Flamegraphs, treemaps, dependency matrices
- Test node type and `tests` edge type
- Configuration file nodes
- `reads`, `writes`, `allocates`, `locks` edge types
