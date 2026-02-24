# Semantic Edges & Node Icons for C3/C2 Layers

## Problem

On C4, edges represent literal code calls/imports — clear and correct. On C3 (component) and C2 (container) layers, edges are just aggregated C4 edges resolved to parent meshes. They carry no architectural meaning — you can't tell that "auth validates tokens from api" vs "config reads from database."

## Solution

Three changes:

1. **Agent-driven enrichment** — existing skills auto-generate `semantic.json`
2. **Circuit-style directional arrows** — orthogonal routed edges with verb-phrase labels on C3/C2
3. **Category icon sprites** — recognizable architecture symbols above C3/C2 nodes

## 1. Agent Enrichment (semantic.json)

The `/prism-diff` and `/prism-impact` skills get an additional final step. After writing `diff.json`, the agent:

1. Reads `nodes.json` + `edges.json`
2. Aggregates C4 edges into component-to-component and container-to-container pairs
3. For each pair: counts edges by type, notes function names and roles involved
4. Generates a 2-4 word verb phrase describing the relationship (e.g. "authenticates against")
5. Assigns each C3/C2 node a category from a fixed set
6. Writes `.callgraph/semantic.json`

### Data Format

```json
{
  "edges": [
    {
      "from": "dir:src/auth",
      "to": "dir:src/database",
      "label": "authenticates against",
      "weight": 10,
      "types": {"calls": 8, "imports": 2}
    }
  ],
  "node_categories": {
    "dir:src/auth": "auth",
    "dir:src/database": "database",
    "dir:src/api": "api"
  }
}
```

### Fixed Category Set

`api`, `auth`, `database`, `ui`, `config`, `util`, `core`, `test`, `model`, `service`

## 2. Circuit-Style Directional Arrows (Viewer)

When `semantic.json` exists, C3/C2 edges render as orthogonal routed paths instead of Bezier curves.

### Routing

- Exit source node horizontally from its edge
- Turn 90 degrees vertical to reach the target's plane
- Turn 90 degrees horizontal to enter the target node
- L-shaped or Z-shaped paths with right-angle bends (like PCB traces)

### Geometry

- Line segments along routed waypoints using `THREE.BufferGeometry`
- Thickness via `THREE.TubeGeometry` (WebGL `linewidth` is unreliable) proportional to `weight`, clamped to min/max
- Arrowhead: `THREE.ConeGeometry` at target end, oriented along final segment direction
- Color: role-based — data flow (cyan), control flow (orange), mixed (gray)

### Labels

- `THREE.Sprite` with `THREE.CanvasTexture` at the midpoint of the longest segment
- Billboard-facing (always readable)
- Semi-transparent background pill for contrast
- Shows the verb phrase from `semantic.json`

### Behavior

- Only render when C3 or C2 layer is visible
- Hovering a semantic edge highlights the underlying C4 edges
- Edge type toggles in config panel still apply
- If `semantic.json` missing, fall back to current thin-line rendering

## 3. Category Icon Sprites (Viewer)

C3/C2 nodes get a recognizable architecture icon floating above them.

### Rendering

- Canvas-rendered texture → `THREE.SpriteMaterial` → `THREE.Sprite`
- Positioned above node top face (Y offset = half node height + gap)
- Monochrome silhouette on subtle circular background tinted with layer color
- Consistent visual size regardless of zoom

### Icon Map

| Category   | Symbol              |
|------------|---------------------|
| `database` | Cylinder (DB drum)  |
| `api`      | Cloud with arrows   |
| `auth`     | Shield              |
| `ui`       | Browser window      |
| `service`  | Hexagon             |
| `config`   | Wrench              |
| `model`    | Stacked rectangles  |
| `core`     | Diamond             |
| `util`     | Toolbox             |
| `test`     | Checkmark badge     |

### Fallback

Nodes without a category in `semantic.json` get no icon. Node mesh shape stays as box for all categories.
