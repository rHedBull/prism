# Diff Between Commits & Change Planning — Design Document

**Date:** 2026-02-20
**Status:** Approved
**Scope:** Structural diff engine, git commit diffing, change plan preview, frontend overlay

---

## Overview

Two features that share a core graph diff engine:

1. **Diff Between Commits** — compare two git refs and visualize what changed structurally at C3+ level
2. **Change Planning** — describe planned changes in a JSON spec, preview their architectural impact on the graph

Both produce the same output format (`diff.json`) consumed by a single frontend overlay.

## Goals

- See the structural impact of a changeset at a glance (PR review, release comparison)
- Preview planned changes (new features, refactors) before writing code
- Operate at component level (C3) and above — architectural impact, not code-level noise

## Non-goals (v1)

- C4 code-level diffs (individual functions/classes in the diff output)
- Animated morph transitions between states
- Side-by-side split view
- Drag-and-drop interactive planning
- Edge classification (data vs control) in diff context

---

## 1. Graph Diff Engine

New module: `src/callgraph/graph_diff.py`

Pure function that compares two graph snapshots and produces a structural diff filtered to C3+ nodes.

### Input

Two graph dicts, each with `nodes` and `edges` arrays (the standard `build_graph` output).

### Output

```json
{
  "meta": {
    "source": "commits",
    "ref_a": "main",
    "ref_b": "feature/payments"
  },
  "summary": {
    "added_nodes": 3,
    "removed_nodes": 1,
    "moved_nodes": 0,
    "modified_nodes": 5,
    "added_edges": 4,
    "removed_edges": 2
  },
  "added_nodes": [
    {
      "id": "file:backend/services/payment_service.py",
      "name": "payment_service.py",
      "abstraction_level": 2,
      "lines_of_code": 150
    }
  ],
  "removed_nodes": [
    {
      "id": "file:backend/utils/legacy_checkout.py",
      "name": "legacy_checkout.py",
      "abstraction_level": 2,
      "lines_of_code": 80
    }
  ],
  "moved_nodes": [],
  "modified_nodes": [
    {
      "id": "file:backend/services/user_service.py",
      "changes": {
        "lines_of_code": [120, 185],
        "export_count": [4, 6]
      }
    }
  ],
  "added_edges": [
    {
      "from": "file:backend/api/payment_routes.py",
      "to": "file:backend/services/payment_service.py",
      "type": "imports"
    }
  ],
  "removed_edges": [
    {
      "from": "file:backend/api/checkout_routes.py",
      "to": "file:backend/utils/legacy_checkout.py",
      "type": "imports"
    }
  ]
}
```

### Filtering

Only nodes with `abstraction_level >= 1` appear in the diff output. C4 code-level nodes (functions, classes — `abstraction_level == 0`) are used internally to compute edge weight changes between file-level nodes, but are not emitted.

### Node matching

- Primary match: `file_path` field (stable across renames within the same path)
- Move detection: if a node disappears from path A and a node with the same `name` appears at path B, classify as moved
- Modified detection: same `file_path` but different `lines_of_code`, `export_count`, or edge set

### Edge matching

Edges matched by `(from, to, type)` tuple. Weight changes on existing edges are not tracked in v1.

---

## 2. Diff Between Commits

### CLI command

```
callgraph diff <ref-a> <ref-b>
```

Where `ref-a` and `ref-b` are any git ref (commit hash, branch, tag, `HEAD~3`, etc.).

### Process

1. Save current git state (`git stash` if working tree is dirty, record current branch)
2. `git checkout <ref-a>` → run `build_graph()` → snapshot A
3. `git checkout <ref-b>` → run `build_graph()` → snapshot B
4. Restore original state (`git checkout <original-branch>`, `git stash pop` if needed)
5. Pass both snapshots through the graph diff engine
6. Write output to `.callgraph/diff.json`

### Safety

- All git operations in a subprocess
- If any step fails, restore original state before raising the error
- No modifications to actual source files — only the parser output is used
- Working tree dirt is preserved via stash/pop

### Output

`.callgraph/diff.json` — the diff engine output format described in section 1.

---

## 3. Change Planning

### Concept

User writes a JSON spec describing planned architectural changes. The system applies those operations to a virtual copy of the current graph, then diffs current vs. modified to show impact.

### Spec file location

`.callgraph/plans/<name>.json`

### Spec format

```json
{
  "name": "add-payment-system",
  "description": "New payment processing service with Stripe integration",
  "operations": [
    {
      "op": "add",
      "name": "PaymentService",
      "layer": "C2",
      "depends_on": [
        "file:backend/services/user_service.py",
        "file:backend/models/order.py"
      ]
    },
    {
      "op": "add",
      "name": "PaymentRoutes",
      "layer": "C1",
      "depends_on": [
        "file:backend/services/payment_service.py"
      ]
    },
    {
      "op": "remove",
      "id": "file:backend/utils/legacy_checkout.py"
    },
    {
      "op": "move",
      "id": "file:backend/utils/billing.py",
      "to_layer": "C2"
    }
  ]
}
```

### Operations

**`add`** — Insert a new node into the graph:
- `name`: display name for the new component
- `layer`: C1, C2, or C3 — maps to `abstraction_level` (C1=3, C2=2, C3=1)
- `depends_on`: list of existing node IDs — creates `imports` edges from the new node to these targets

**`remove`** — Delete a node and all its edges:
- `id`: exact graph node ID

**`move`** — Relocate a node to a different layer:
- `id`: exact graph node ID
- `to_layer`: target layer (C1, C2, C3) — recomputes `abstraction_level`
- Existing edges stay attached

### Node ID discovery

New CLI command to find IDs for use in specs:

```
callgraph list [--layer C1|C2|C3]
```

Prints node IDs filtered to C3+ by default, with name and layer for readability:

```
C1  file:backend/api/auth_routes.py          auth_routes.py
C1  file:backend/api/user_routes.py          user_routes.py
C2  file:backend/services/auth_service.py    auth_service.py
C2  file:backend/services/user_service.py    user_service.py
C3  file:backend/models/user.py              user.py
```

### CLI command

```
callgraph plan <spec-file>
```

### Process

1. Load current graph from `.callgraph/nodes.json` and `.callgraph/edges.json`
2. Deep-copy the graph
3. Apply each operation to the copy:
   - `add`: insert node, create `imports` edges from `depends_on`, create `contains` edge from inferred parent directory
   - `remove`: delete node and all connected edges
   - `move`: update `abstraction_level`, update `parent` if layer implies different directory grouping
4. Run diff engine: original graph vs. modified graph
5. Write `.callgraph/diff.json` with `meta.source = "plan"` and `meta.plan_name`

### Output

Same `.callgraph/diff.json` format. The `meta` field distinguishes it:

```json
{
  "meta": {
    "source": "plan",
    "plan_name": "add-payment-system"
  }
}
```

---

## 4. Frontend — Diff Overlay

New module: `web/js/diff-overlay.js`

The frontend is agnostic to whether the diff came from commits or a plan. It reads `diff.json` and renders the overlay.

### Activation

On load, `graph-loader.js` checks for `.callgraph/diff.json`. If present, passes the data to `diff-overlay.js` which activates diff mode.

### Color scheme

| Diff state | Node treatment | Edge treatment |
|---|---|---|
| Added | Green glow (`#4CAF50`), full opacity | Solid green line |
| Removed | Red glow (`#F44336`), semi-transparent ghost at old position | Dashed red line, fading out |
| Modified | Yellow glow (`#FFC107`), full opacity | — |
| Moved | Blue glow (`#2196F3`), animated slide from old to new position | Edges reattach |
| Unchanged | Dimmed to ~30% opacity | Dimmed to ~30% opacity |

Dimming unchanged nodes makes the diff pop visually.

### Summary panel

Floating box in top-left corner, matching existing info panel style (dark, semi-transparent background):

For commits:
```
Diff: main..feature/payments
  +3 components  -1 component  ~5 modified
```

For plans:
```
Plan: add-payment-system
  +2 components  -1 component  ~0 modified
```

### Hover behavior

When hovering a modified node in diff mode, the info panel shows edge-level diff details:
- "New dependency: → PaymentService"
- "Removed dependency: → LegacyCheckout"

### Controls

- "Clear diff" button — removes the overlay, returns to normal view
- Diff mode is compatible with existing camera controls, layer toggles, and color modes

### Layout

Added nodes are positioned by the existing force layout like any other node. No new layout engine needed. Removed nodes retain their last known position as ghost outlines.

---

## 5. Architecture

```
                        ┌──────────────────┐
                        │   diff.json      │
                        │  (shared format)  │
                        └────────▲─────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
            ┌───────┴───────┐        ┌────────┴────────┐
            │  diff command  │        │  plan command   │
            │ (two git refs) │        │ (spec file)     │
            └───────┬───────┘        └────────┬────────┘
                    │                         │
                    │   snapshot A + B         │  current + virtual
                    │                         │
                    └────────────┬────────────┘
                                 │
                        ┌────────▼─────────┐
                        │  Graph Diff      │
                        │  Engine          │
                        │  (C3+ filter)    │
                        └────────┬─────────┘
                                 │
                        ┌────────▼─────────┐
                        │  diff.json       │
                        └────────┬─────────┘
                                 │
                        ┌────────▼─────────┐
                        │  Frontend        │
                        │  Diff Overlay    │
                        └──────────────────┘
```

Three layers:
1. **Graph diff engine** — shared core, compares two graph snapshots at C3+
2. **Two producers** — `diff` command (git checkouts → two real snapshots) and `plan` command (current graph + spec → virtual snapshot)
3. **One consumer** — frontend diff overlay, agnostic to source

---

## 6. Files Changed

### New files

| File | Purpose |
|---|---|
| `src/callgraph/graph_diff.py` | Diff engine — takes two graphs, returns C3+ structural diff |
| `src/callgraph/plan_engine.py` | Reads plan JSON, applies operations to graph copy, calls diff engine |
| `web/js/diff-overlay.js` | Reads `diff.json`, applies color overlay, renders summary panel |

### Modified files

| File | Change |
|---|---|
| `src/callgraph/cli.py` | Add `diff`, `plan`, and `list` subcommands |
| `src/callgraph/graph_builder.py` | Allow `build_graph` to target arbitrary directories (for git checkout snapshots) |
| `src/callgraph/output.py` | Add `write_diff()` to serialize `diff.json` |
| `web/js/graph-loader.js` | Check for `diff.json` on load, pass diff data to overlay module |
| `web/js/layers.js` | Support dimming unchanged nodes when diff mode active |
| `web/js/interaction.js` | Show edge diff details in info panel on hover |
| `web/index.html` | Add "Clear diff" button, summary panel container |

### Unchanged files

`web/js/edges.js`, `web/js/layout.js`, `web/js/scene.js`, `web/js/tree-panel.js`, `web/js/config-panel.js`

### Test files

| File | Coverage |
|---|---|
| `tests/test_graph_diff.py` | Diff engine: added/removed/moved/modified detection, C3+ filtering, edge matching |
| `tests/test_plan_engine.py` | Plan operations: add/remove/move, edge creation, layer mapping, ID validation |
