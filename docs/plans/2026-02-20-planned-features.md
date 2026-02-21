# Prism — Planned Features

**Date:** 2026-02-20
**Status:** Draft — feature backlog for post-MVP

---

## 1. Diff Between Commits

Compare two git commits (or branches, tags) and visualize what changed structurally.

### Data model
- New CLI command: `callgraph diff <commit-a> <commit-b>`
- Runs `build_graph` at each commit (checkout or git-show), produces two graph snapshots
- Diff engine emits:
  - **Added nodes** — new files, functions, classes
  - **Removed nodes** — deleted entities
  - **Modified nodes** — LOC changed, signature changed, moved to different parent
  - **Added/removed edges** — new imports, calls, broken dependencies
  - **Moved nodes** — same entity, different file/directory (rename detection)

### Visualization
- Color overlay on existing 3D view: green = added, red = removed, yellow = modified, blue = moved
- Edge diff: new edges glow, removed edges shown as dashed/ghosted
- Slider or toggle to scrub between "before" and "after" states
- Summary panel: "14 functions added, 3 removed, 8 modified, 2 files moved"
- Animated morph transition between the two graph states

### Use cases
- PR review: see structural impact of a changeset at a glance
- Refactoring validation: confirm a refactor only moved/renamed, didn't change dependencies
- Regression hunting: what changed between two releases

---

## 2. Refactoring Planning

Overlay that identifies refactoring candidates and lets you plan moves interactively.

### Analysis
- **God files** — files with high LOC + high fan-in/fan-out
- **Circular dependencies** — cycles in the import graph, highlighted as red loops
- **Misplaced abstractions** — nodes whose edges mostly connect to a different layer than the one they're on
- **Orphan nodes** — functions/classes with zero incoming edges (dead code candidates)
- **High coupling clusters** — groups of files with dense cross-edges that could be extracted into a module
- **Layer violations** — edges that skip abstraction levels (e.g., C1 directly calling C4)

### Interactive planning
- Drag-and-drop a node to a different layer/directory in the 3D view → preview what the graph would look like
- Show "what-if" edge changes: which edges break, which new ones form
- Export a refactoring plan as a structured markdown/JSON checklist

---

## 3. Data vs Control Separation

Classify and visually distinguish data flow from control flow.

### Classification
- **Data nodes**: types, interfaces, schemas, models, DTOs, config objects, database entities
- **Control nodes**: functions, handlers, middleware, controllers, orchestrators, state machines
- **Hybrid nodes**: classes that hold both data and behavior (flagged for review)

### Edge classification
- **Data edges**: type references, schema imports, model usage, serialization
- **Control edges**: function calls, event dispatch, middleware chains, route handlers

### Visualization
- Dual-color scheme: data = cool tones (blue/cyan), control = warm tones (orange/red)
- Toggle to show only data flow or only control flow
- "Data layer" vs "Control layer" split view — same nodes, different edge sets
- Useful for understanding: where does data originate, how does it transform, where does it exit

---

## 4. Infrastructure — What Lives/Runs Where

Map code entities to their runtime deployment targets.

### Metadata sources
- Parse `Dockerfile`, `docker-compose.yml`, `kubernetes/*.yml`, `serverless.yml`, `Procfile`
- Parse CI/CD configs: `.github/workflows/*.yml`, `Jenkinsfile`, `.gitlab-ci.yml`
- Parse package.json scripts, pyproject.toml entry points
- Detect: frontend bundle, backend server, worker process, cron job, lambda, database migration

### Data model
- New node type: `runtime` — represents a deployment unit (container, lambda, service)
- New edge type: `deployed_in` — links code modules to their runtime
- New node type: `infrastructure` — database, queue, cache, CDN, API gateway

### Visualization
- Runtime nodes rendered as large translucent shells enclosing the code they contain
- Infrastructure nodes as distinct shapes (cylinder = database, diamond = queue, cloud = CDN)
- Network edges between runtimes: HTTP calls, queue messages, shared database
- "Deployment view" — hide code detail, show only runtime topology
- Color by environment: dev = green, staging = yellow, production = red

---

## 5. Data Streams

Trace how data flows through the system end-to-end.

### Detection
- Follow type references: where is a type defined → where is it instantiated → where is it read
- Trace function return types through call chains
- Detect transformation points: where data shape changes (serialization, mapping, aggregation)
- Identify data sources (DB reads, API inputs, file reads) and sinks (DB writes, API responses, file writes)

### Visualization
- Animated particles flowing along edges to show data direction
- Particle color = data type/schema
- Thicker streams = higher throughput (by call frequency or LOC weight)
- Click a type/model → highlight its full journey from source to sink
- "Data lineage" mode: select an output → trace backwards to all inputs

---

## 6. Technologies Used

Visual breakdown of the tech stack across the codebase.

### Detection
- Parse dependency files: `package.json`, `requirements.txt`, `pyproject.toml`, `go.mod`, `Cargo.toml`
- Detect frameworks from import patterns (FastAPI, React, Express, Django, etc.)
- Detect infrastructure SDKs (AWS SDK, GCP client, Redis client, etc.)
- Count usage: how many files import each dependency

### Visualization
- "Tech radar" overlay: concentric rings showing core → common → peripheral dependencies
- Node tinting by primary framework (React = blue, FastAPI = green, etc.)
- Technology legend in sidebar
- Filter view: "show me only files that use Redis" → highlight those, fade the rest
- Dependency version health: outdated = yellow, deprecated = red, current = green

---

## 7. User / API Journeys

Trace a request or user action through the entire stack.

### Definition
- A journey = ordered sequence of function calls triggered by an entry point
- Entry points: API route handler, event listener, CLI command, UI component mount
- Auto-detect from route definitions (`@app.get("/users")`, `router.post(...)`, etc.)

### Visualization
- Select an entry point → animate the call chain lighting up in sequence
- Each step shows: function name, file, layer, what data it touches
- Cross-service journeys: follow HTTP calls, queue messages, event emissions
- Journey catalog: list all detected entry points, click to trace any one
- Side panel: sequential list of steps with timing estimates (LOC-based heuristic)

---

## 8. Animated Journeys

Cinematic walkthroughs of journeys and system behavior.

### Modes
- **Request trace**: camera follows a request through the layers, top to bottom
- **Data lifecycle**: follow a data entity from creation through transformations to final state
- **Build pipeline**: show how source files flow through build/bundle/deploy stages
- **Error propagation**: trace an error from origin through catch blocks and handlers

### Camera behavior
- Auto-pilot: camera smoothly flies between nodes as the journey progresses
- Speed control: play/pause, 0.5x/1x/2x
- Step-by-step: advance one hop at a time with spacebar
- Narration panel: text description of what's happening at each step

### Visual effects
- Glowing trail along the path already traversed
- Pulse effect on the currently active node
- Fade out everything not on the current journey
- Particle stream showing data/request flowing along edges

---

## 9. Fly-Through

Free-form cinematic camera paths through the 3D codebase.

### Predefined paths
- **Overview orbit**: slow 360 rotation around the full stack
- **Layer descent**: start high above C1, descend through each layer to C4
- **Dependency river**: follow the densest edge bundle from source to sink
- **Hotspot tour**: visit the top N most-connected nodes in sequence

### Custom paths
- Record mode: manually fly the camera, record keyframes
- Waypoint editor: place camera waypoints, system interpolates smooth path
- Export as video/GIF for presentations and documentation

### Controls
- Play/pause/scrub timeline
- Speed slider
- Loop toggle
- "Scenic mode": auto-fly with ambient rotation, useful for lobby screens or demos

---

## 10. Fixed Views / Presets

One-click camera presets for common perspectives.

### Standard views
- **Isometric overview** (current default): 45-degree angle, see all layers
- **Top-down per layer**: orthographic camera directly above one layer
- **Side profile**: see the stack from the side, emphasizing cross-layer edges
- **Front elevation**: flat view of a single layer's force layout
- **Split view**: two viewports side-by-side (e.g., backend vs frontend, or before vs after)

### Top-down per layer
- Dropdown or tab bar to select layer (C1/C2/C3/C4)
- Orthographic camera, no perspective distortion
- Nodes shown as 2D rectangles (top of their 3D boxes)
- Edges as flat curves within the plane
- Good for: reviewing layout within one abstraction level, spotting clustering patterns

### Persistence
- Save/load custom view presets
- URL-encoded view state for sharing specific perspectives

---

## 11. Hide / Show All

Global visibility controls for every element type.

### Toggles
- **By node type**: directories, files, functions, classes, interfaces
- **By layer**: C1, C2, C3, C4 individually
- **By language**: Python, TypeScript, JavaScript
- **By edge type**: imports, calls, contains, inherits_from
- **By file pattern**: glob filter (e.g., `**/test_*`, `**/*.spec.ts`)

### UI
- Sidebar panel with checkbox tree:
  ```
  ▾ Layers
    ☑ C1 — Context
    ☑ C2 — Container
    ☑ C3 — Component
    ☐ C4 — Code          ← hidden
  ▾ Edge types
    ☑ imports
    ☑ calls
    ☐ contains            ← hidden
  ▾ Languages
    ☑ Python
    ☑ TypeScript
  ```
- "Solo" button: click to show ONLY that category, hide all others
- "Show all" / "Hide all" master toggles
- Keyboard shortcuts: `1`-`4` toggle layers, `e` toggle edges, `f` toggle functions

### Behavior
- Hidden elements animate out (fade + shrink), not instant disappear
- Edges auto-hide when either endpoint is hidden
- Hidden state preserved across view changes

---

## 12. Highlight Options

Rich selection and emphasis tools beyond current hover behavior.

### Selection modes
- **Single select**: click a node (current behavior, enhanced)
- **Multi-select**: ctrl+click to add nodes to selection
- **Lasso select**: drag a rectangle to select all nodes within
- **Path select**: click two nodes → highlight shortest path between them
- **Subtree select**: click a node → select all its descendants across layers
- **Regex select**: type a pattern → highlight all matching node names

### Highlight styles
- **Focus**: selected nodes full opacity, everything else at 10%
- **Glow**: selected nodes get emissive glow ring
- **Isolate**: hide everything except selected nodes and their direct connections
- **Heatmap**: color nodes by metric (LOC, fan-in, fan-out, change frequency)
- **Trace**: animated particles flowing along edges connected to selection

### Persistence
- Pin a highlight: keep it active while exploring elsewhere
- Stack highlights: apply multiple highlight layers with different colors
- Named highlights: save a selection as "auth flow", "data pipeline", etc.

---

## 13. Groupings

Custom and automatic node grouping beyond the directory hierarchy.

### Automatic groupings
- **By directory** (current): directory containment hierarchy
- **By language**: group all Python files, all TS files
- **By framework**: React components, FastAPI routes, utility functions
- **By dependency cluster**: strongly-connected components in the import graph
- **By change frequency**: files that change together (from git history) grouped together
- **By author/team**: files primarily maintained by the same contributor(s)

### Custom groupings
- Create named groups: drag nodes into a group, or define by glob/regex
- Groups rendered as translucent bounding boxes in the 3D view
- Group-level edges: collapse a group to a single node, show inter-group edges
- Nested groups: groups within groups

### Group operations
- Collapse/expand: toggle between seeing group contents and seeing the group as one block
- Compare groups: side-by-side view of two groups' internal structure
- Group metrics: total LOC, edge count, avg complexity
- Color groups: assign colors to groups for visual distinction

### Use cases
- "Show me the auth system" → custom group of all auth-related files
- "Compare frontend vs backend complexity" → two groups side by side
- "Which modules are tightly coupled?" → auto-detected dependency clusters

---

## Implementation Priority

| Priority | Feature | Complexity | Dependencies |
|----------|---------|-----------|--------------|
| P0 | Hide/Show All | Medium | Sidebar UI |
| P0 | Fixed Views / Top-down | Medium | Camera presets |
| P0 | Highlight Options (multi-select, path) | Medium | Selection system |
| P1 | Groupings (auto by directory/language) | Medium | Group renderer |
| P1 | Technologies Used | Low | Dependency parser |
| ~~P1~~ | ~~Diff Between Commits~~ | ~~High~~ | ~~Done~~ — `callgraph diff`, `/prism-diff`, `/prism-impact` |
| ~~P1~~ | ~~Metric-Driven Block Size & Color~~ | ~~Medium~~ | ~~Done~~ — complexity-aware sizing, color by any metric, relative to visible blocks |
| ~~P1~~ | ~~Additional Metrics~~ | ~~Medium~~ | ~~Done~~ — cyclomatic complexity, param count, nesting depth, instability, coupling, node type, None option |
| P2 | User / API Journeys | High | Route detection, call chain tracing |
| P2 | Data vs Control Separation | Medium | Node/edge classifier |
| P2 | Data Streams | High | Type flow analysis |
| P2 | Animated Journeys | Medium | Journey system (P2 dep) |
| P3 | Fly-Through | Medium | Camera path recorder |
| P3 | Infrastructure | High | Config file parsers |
| P3 | Refactoring Planning | High | Analysis engine, interactive drag |
