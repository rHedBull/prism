# Data vs Control Separation — Design Document

**Date:** 2026-02-20
**Updated:** 2026-02-21
**Status:** Approved
**Scope:** v1 — node classification and color mode toggle

---

## Overview

Add a `role` field to every node in the graph that classifies it as **data**, **control**, or **hybrid**. The Three.js frontend gets a color mode toggle that re-colors all blocks by role instead of by language.

## Goals

- See at a glance which parts of a codebase define data structures vs orchestrate behavior
- Reveal architecture health: well-structured code separates data from control; mixed layers signal design smells
- Lay groundwork for future data-flow tracing and edge classification

## Non-goals (v1)

- Edge classification (data edge vs control edge)
- Isolation mode (hide data-only or control-only)
- Configurable classification rules
- AST-deep analysis beyond base classes and call counts

---

## 1. Classification Rules

Each node gets `role`: `"data"` | `"control"` | `"hybrid"`.

### TypeScript / JavaScript

| AST node type | Role | Reasoning |
|---------------|------|-----------|
| `interface_declaration` | data | Pure type definition, no runtime behavior |
| `type_alias_declaration` | data | Type alias, no runtime behavior |
| `class_declaration` | hybrid | Has both shape and behavior |
| Function with 0 calls | data | Pure accessor/transform |
| Function with 1+ calls | control | Orchestrates other code |

### Python

| Signal | Role | Reasoning |
|--------|------|-----------|
| Class with `@dataclass` decorator | data | Explicit data container |
| Class inheriting `BaseModel`, `TypedDict`, `NamedTuple`, `Enum` | data | Known data base classes |
| Class — other | hybrid | Could be either |
| Function with 0 calls | data | Pure transform |
| Function with 1+ calls | control | Orchestrates |

### Aggregated nodes (files, directories)

Majority vote: if >60% of child nodes are data, the file/directory is data. If >60% control, it's control. Otherwise hybrid.

---

## 2. Parser Changes

### Python parser (`python_parser.py`)

Extract two new fields on class nodes:

- **`decorators`**: list of decorator names (e.g., `["dataclass", "validator"]`)
  - Source: `decorator` child nodes of `class_definition`
- **`bases`**: list of base class names (e.g., `["BaseModel"]`)
  - Source: `argument_list` child of `class_definition` (the superclass list)

### TypeScript parser (`typescript_parser.py`)

The parser already detects `interface_declaration` and `type_alias_declaration` separately (since the metrics feature added `cyclomatic_complexity`, `param_count`, `max_nesting` to all nodes). However, it still emits `type: "class"` for all three. Change to emit distinct types:

| AST node type | Emitted `type` field |
|---------------|---------------------|
| `interface_declaration` | `"interface"` |
| `type_alias_declaration` | `"type_alias"` |
| `class_declaration` | `"class"` |

This is a **schema change** — downstream code that filters on `type === "class"` must also match `"interface"` and `"type_alias"`. Affected files:
- `web/js/graph-loader.js` — `groupByAbstractionLevel` filters on `node.type === 'class'` (line 91)
- `web/js/config-panel.js` — node type toggles only list `function` and `class`
- `web/js/metrics.js` — `TYPE_COLORS` map has entries for `function`, `class`, `component`, `container`, `system`
- `web/index.html` — node type checkboxes only list Functions and Classes

---

## 3. Graph Builder Changes

### New function: `classify_roles(nodes)`

Located in `graph_builder.py`, runs after all nodes and edges are built.

```
classify_roles(nodes):
    for node in nodes:
        if node.type in ("interface", "type_alias"):
            node.role = "data"
        elif node.type == "class":
            if has_data_base(node):       # BaseModel, dataclass, etc.
                node.role = "data"
            else:
                node.role = "hybrid"
        elif node.type == "function":
            if len(node.calls) == 0:
                node.role = "data"
            else:
                node.role = "control"
        elif node.type == "file":
            node.role = majority_vote(children)
        elif node.type == "directory":
            node.role = majority_vote(children)
```

### Known data base classes (Python)

```python
DATA_BASES = {"BaseModel", "TypedDict", "NamedTuple", "Enum", "IntEnum", "StrEnum"}
DATA_DECORATORS = {"dataclass", "dataclasses.dataclass"}
```

### Output

The `role` field appears in `nodes.json`:

```json
{
    "id": "func:backend/services/auth_service.py:authenticate_user",
    "type": "function",
    "role": "control",
    ...
}
```

No changes to `edges.json`.

---

## 4. Frontend Changes

### Color scheme

| Role | Color | Hex |
|------|-------|-----|
| data | Teal green | `#26A69A` |
| control | Warm orange | `#FF7043` |
| hybrid | Muted slate | `#78909C` |

### Integration with existing metrics system

Since the metrics feature landed, color is already controlled by a dropdown in the config panel (`web/js/metrics.js`). The `role` classification integrates as a new **categorical color metric** — not a separate toggle.

**Add `"role"` as a new option in the color dropdown** (`metric-color` select in `index.html`), alongside `language`, `type`, etc.

In `metrics.js`:
- Add `ROLE_COLORS` map: `{ data: 0x26A69A, control: 0xFF7043, hybrid: 0x78909C }`
- Add `"role"` to `COLOR_METRICS` array
- Handle `_colorMetric === 'role'` in `computeColor()` — return `ROLE_COLORS[node.role]`

No separate toggle or legend needed — the existing dropdown and metric infrastructure handles it.

### Graph loader compatibility

Update `graph-loader.js` to handle the new node types (`"interface"`, `"type_alias"`) alongside `"class"` when building the C4 code layer (line 91). Treat all three the same way for layer grouping — they're all code-level entities.

### Config panel compatibility

Update node type toggles to include `interface` and `type_alias`:
- `web/index.html` — add checkboxes for Interfaces and Type Aliases
- `web/js/config-panel.js` — add toggle handlers for the new types
- `web/js/metrics.js` — add `interface` and `type_alias` entries to `TYPE_COLORS`

---

## 5. Connection to Data Streams

This feature is the foundation for the planned **Data Streams** feature (animated data lineage). The `role` classification defines where data streams start, flow through, and end:

```
data node (source)  →  control node  →  control node  →  ...  →  data node (sink)
     UserSchema          create_user()     db.save()            UserResponse
```

- **Data nodes become sources and sinks.** A `UserSchema` (role=data) is where a stream originates. A `UserResponse` (role=data) is where it terminates.
- **Control nodes become the plumbing.** Functions with role=control that import a data node and call other control nodes form the pipeline steps between source and sink.
- **A data stream is a path: data → [control chain] → data.** Select a data node, follow edges into control nodes, follow their call chains, stop when you hit another data node. That's one complete stream.

Without the role classification, there's no way to distinguish stream endpoints from pipeline steps — every node looks the same. The `role` field makes stream computation a graph traversal with clear start/stop conditions.

**v1 (this feature):** classify nodes — you can *see* the data/control separation.
**v2 (Data Streams):** use that classification to *compute* data→control→...→control→data paths and animate particles along them.

---

## 6. Files Changed

| File | Change |
|------|--------|
| `src/callgraph/parsers/python_parser.py` | Extract `decorators` and `bases` on class nodes |
| `src/callgraph/parsers/typescript_parser.py` | Emit `"interface"` and `"type_alias"` types |
| `src/callgraph/graph_builder.py` | Add `classify_roles()` pass, call after `build_graph` |
| `src/callgraph/output.py` | No change — already serializes all node fields |
| `web/js/graph-loader.js` | Handle new node types in C4 layer grouping |
| `web/js/metrics.js` | Add `ROLE_COLORS`, handle `role` in `computeColor()`, add to `COLOR_METRICS` |
| `web/js/config-panel.js` | Add toggle handlers for `interface` and `type_alias` node types |
| `web/index.html` | Add `role` to color dropdown, add interface/type_alias checkboxes |
| `tests/` | Update tests for new fields and classification |
