# Semantic Edges & Node Icons Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add LLM-generated semantic edge labels and category icon sprites to C3/C2 layers in the prism viewer, with agent-driven enrichment integrated into existing skills.

**Architecture:** The viewer loads an optional `semantic.json` alongside `nodes.json`/`edges.json`. A new `semantic-edges.js` module renders circuit-style orthogonal arrows with text labels. A new `node-icons.js` module renders canvas-drawn icon sprites above C3/C2 nodes. The `/prism-diff` and `/prism-impact` skills gain a final enrichment step where the agent writes `semantic.json`.

**Tech Stack:** Three.js (TubeGeometry, ConeGeometry, CanvasTexture, Sprite), existing graph-loader.js data pipeline, Claude Code skill markdown.

---

### Task 1: Load semantic.json in graph-loader.js

**Files:**
- Modify: `web/js/graph-loader.js:3-11`

**Step 1: Add semantic.json fetch to loadGraph**

In `loadGraph()`, add a third fetch for `semantic.json` that gracefully returns `null` if not found:

```javascript
export async function loadGraph(basePath = '.') {
    const [nodesRes, edgesRes] = await Promise.all([
        fetch(`${basePath}/.callgraph/nodes.json`),
        fetch(`${basePath}/.callgraph/edges.json`),
    ]);
    const nodes = await nodesRes.json();
    const edges = await edgesRes.json();

    // Optional semantic enrichment
    let semantic = null;
    try {
        const semRes = await fetch(`${basePath}/.callgraph/semantic.json`);
        if (semRes.ok) semantic = await semRes.json();
    } catch (_) { /* no semantic data available */ }

    return { nodes, edges, semantic };
}
```

**Step 2: Verify no breakage**

Run: `callgraph serve` and confirm viewer still loads without a `semantic.json` present.

**Step 3: Commit**

```bash
git add web/js/graph-loader.js
git commit -m "feat: load optional semantic.json in graph loader"
```

---

### Task 2: Create semantic-edges.js — circuit-style arrow rendering

**Files:**
- Create: `web/js/semantic-edges.js`

**Step 1: Create the module**

```javascript
import * as THREE from 'three';

const ROLE_COLORS = {
    data: 0x00E5CC,
    control: 0xFF6B35,
    mixed: 0x9E9E9E,
};

const TUBE_RADIUS_MIN = 0.08;
const TUBE_RADIUS_MAX = 0.35;
const WEIGHT_MAX = 30;
const ARROWHEAD_LENGTH = 0.8;
const ARROWHEAD_RADIUS = 0.3;

/**
 * Create circuit-style orthogonal edges for C3/C2 semantic relationships.
 * Returns array of THREE.Group objects (each group = tube + arrowhead + label).
 */
export function createSemanticEdges(semanticData, nodeMeshes, scene) {
    if (!semanticData || !semanticData.edges) return [];

    const edgeGroups = [];

    for (const edge of semanticData.edges) {
        const fromMesh = nodeMeshes[edge.from];
        const toMesh = nodeMeshes[edge.to];
        if (!fromMesh || !toMesh) continue;
        if (fromMesh === toMesh) continue;

        const group = new THREE.Group();
        group.userData = { type: 'semantic-edge', edgeData: edge };

        const start = fromMesh.position.clone();
        const end = toMesh.position.clone();

        // Determine edge role from dominant edge types
        const types = edge.types || {};
        const callWeight = types.calls || 0;
        const importWeight = types.imports || 0;
        const role = callWeight > importWeight ? 'control' : importWeight > callWeight ? 'data' : 'mixed';
        const color = ROLE_COLORS[role] || ROLE_COLORS.mixed;

        // Build orthogonal waypoints (circuit routing)
        const waypoints = computeCircuitPath(start, end);

        // Tube thickness from weight
        const t = Math.min((edge.weight || 1) / WEIGHT_MAX, 1);
        const radius = TUBE_RADIUS_MIN + t * (TUBE_RADIUS_MAX - TUBE_RADIUS_MIN);

        // Create tube along waypoints
        const curve = new THREE.CatmullRomCurve3(waypoints, false, 'catmullrom', 0.01);
        const tubeGeo = new THREE.TubeGeometry(curve, 64, radius, 8, false);
        const tubeMat = new THREE.MeshPhongMaterial({
            color,
            transparent: true,
            opacity: 0.7,
            emissive: color,
            emissiveIntensity: 0.1,
        });
        const tube = new THREE.Mesh(tubeGeo, tubeMat);
        group.add(tube);

        // Arrowhead at the end
        const lastSeg = waypoints[waypoints.length - 1].clone().sub(waypoints[waypoints.length - 2]).normalize();
        const arrowGeo = new THREE.ConeGeometry(ARROWHEAD_RADIUS, ARROWHEAD_LENGTH, 8);
        const arrowMat = new THREE.MeshPhongMaterial({ color, emissive: color, emissiveIntensity: 0.15 });
        const arrow = new THREE.Mesh(arrowGeo, arrowMat);
        arrow.position.copy(end);
        // Orient cone along the last segment direction
        const up = new THREE.Vector3(0, 1, 0);
        const quat = new THREE.Quaternion().setFromUnitVectors(up, lastSeg);
        arrow.quaternion.copy(quat);
        group.add(arrow);

        // Label sprite at midpoint of the longest segment
        if (edge.label) {
            const midIdx = Math.floor(waypoints.length / 2);
            const labelPos = waypoints[midIdx].clone();
            labelPos.y += 1.2;
            const sprite = createLabelSprite(edge.label, color);
            sprite.position.copy(labelPos);
            group.add(sprite);
        }

        scene.add(group);
        edgeGroups.push(group);
    }

    return edgeGroups;
}

/**
 * Compute orthogonal (circuit-style) path between two 3D points.
 * Route: exit source horizontally on X → go vertical on Y → enter target horizontally on X.
 * If same Y level: L-shape on XZ plane with a midpoint jog.
 */
function computeCircuitPath(start, end) {
    const sameLayer = Math.abs(start.y - end.y) < 1;

    if (sameLayer) {
        // Same layer: L-shaped or Z-shaped route on the XZ plane
        const midX = (start.x + end.x) / 2;
        return [
            start.clone(),
            new THREE.Vector3(midX, start.y, start.z),
            new THREE.Vector3(midX, end.y, end.z),
            end.clone(),
        ];
    } else {
        // Cross-layer: exit horizontally, go vertical, enter horizontally
        const offsetX = (end.x - start.x) * 0.3;
        const midY = (start.y + end.y) / 2;
        return [
            start.clone(),
            new THREE.Vector3(start.x + offsetX, start.y, start.z),
            new THREE.Vector3(start.x + offsetX, midY, start.z),
            new THREE.Vector3(end.x - offsetX, midY, end.z),
            new THREE.Vector3(end.x - offsetX, end.y, end.z),
            end.clone(),
        ];
    }
}

function createLabelSprite(text, color) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = 512;
    canvas.height = 64;

    // Measure text to size the background pill
    ctx.font = 'bold 24px monospace';
    const metrics = ctx.measureText(text);
    const textW = metrics.width;
    const pillW = textW + 20;
    const pillH = 36;
    const pillX = (canvas.width - pillW) / 2;
    const pillY = (canvas.height - pillH) / 2;

    // Background pill
    ctx.fillStyle = 'rgba(248, 246, 252, 0.85)';
    ctx.beginPath();
    ctx.roundRect(pillX, pillY, pillW, pillH, 6);
    ctx.fill();
    ctx.strokeStyle = `#${new THREE.Color(color).getHexString()}`;
    ctx.lineWidth = 2;
    ctx.stroke();

    // Text
    ctx.fillStyle = `#${new THREE.Color(color).getHexString()}`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, canvas.width / 2, canvas.height / 2);

    const texture = new THREE.CanvasTexture(canvas);
    texture.premultiplyAlpha = true;
    const mat = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false });
    const sprite = new THREE.Sprite(mat);
    sprite.scale.set(10, 1.5, 1);
    return sprite;
}

/**
 * Show/hide semantic edges based on layer visibility.
 */
export function updateSemanticEdgeVisibility(edgeGroups, nodeMeshes) {
    for (const group of edgeGroups) {
        const edge = group.userData.edgeData;
        const fromMesh = nodeMeshes[edge.from];
        const toMesh = nodeMeshes[edge.to];
        group.visible = !!(fromMesh?.visible && toMesh?.visible);
    }
}
```

**Step 2: Commit**

```bash
git add web/js/semantic-edges.js
git commit -m "feat: add semantic-edges.js for circuit-style C3/C2 arrows"
```

---

### Task 3: Create node-icons.js — category icon sprites

**Files:**
- Create: `web/js/node-icons.js`

**Step 1: Create the module**

Each icon is drawn on a canvas as a recognizable silhouette: database cylinder, auth shield, API cloud, etc.

```javascript
import * as THREE from 'three';

const ICON_SIZE = 64;
const SPRITE_SCALE = 2.5;

const ICON_DRAWERS = {
    database: drawDatabaseIcon,
    api: drawApiIcon,
    auth: drawAuthIcon,
    ui: drawUiIcon,
    service: drawServiceIcon,
    config: drawConfigIcon,
    model: drawModelIcon,
    core: drawCoreIcon,
    util: drawUtilIcon,
    test: drawTestIcon,
};

/**
 * Create icon sprites above C3/C2 nodes based on semantic categories.
 * Returns array of sprites added to the scene.
 */
export function createNodeIcons(semanticData, nodeMeshes, scene) {
    if (!semanticData || !semanticData.node_categories) return [];

    const sprites = [];
    const textureCache = {};

    for (const [nodeId, category] of Object.entries(semanticData.node_categories)) {
        const mesh = nodeMeshes[nodeId];
        if (!mesh) continue;

        const drawer = ICON_DRAWERS[category];
        if (!drawer) continue;

        // Cache textures per category
        if (!textureCache[category]) {
            textureCache[category] = createIconTexture(drawer);
        }

        const mat = new THREE.SpriteMaterial({
            map: textureCache[category],
            transparent: true,
            depthWrite: false,
        });
        const sprite = new THREE.Sprite(mat);

        // Position above the node
        const nodeHeight = mesh.geometry?.parameters?.height || 1;
        sprite.position.copy(mesh.position);
        sprite.position.y += nodeHeight / 2 + 1.5;

        sprite.scale.set(SPRITE_SCALE, SPRITE_SCALE, 1);
        sprite.userData = { type: 'node-icon', nodeId, category };

        scene.add(sprite);
        sprites.push(sprite);
    }

    return sprites;
}

function createIconTexture(drawFn) {
    const canvas = document.createElement('canvas');
    canvas.width = ICON_SIZE;
    canvas.height = ICON_SIZE;
    const ctx = canvas.getContext('2d');

    // Circular background
    ctx.fillStyle = 'rgba(248, 246, 252, 0.8)';
    ctx.beginPath();
    ctx.arc(ICON_SIZE / 2, ICON_SIZE / 2, ICON_SIZE / 2 - 2, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = 'rgba(140, 96, 243, 0.4)';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Draw the icon
    ctx.fillStyle = '#353148';
    ctx.strokeStyle = '#353148';
    ctx.lineWidth = 2;
    drawFn(ctx, ICON_SIZE);

    const texture = new THREE.CanvasTexture(canvas);
    texture.premultiplyAlpha = true;
    return texture;
}

// --- Icon draw functions ---
// All draw within a centered area of the ICON_SIZE canvas

function drawDatabaseIcon(ctx, s) {
    // Classic cylinder: top ellipse, body, bottom ellipse
    const cx = s / 2, cy = s / 2;
    const w = s * 0.35, h = s * 0.3;
    const ry = h * 0.3; // ellipse vertical radius

    ctx.beginPath();
    // Top ellipse
    ctx.ellipse(cx, cy - h / 2, w, ry, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Body sides
    ctx.beginPath();
    ctx.moveTo(cx - w, cy - h / 2);
    ctx.lineTo(cx - w, cy + h / 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(cx + w, cy - h / 2);
    ctx.lineTo(cx + w, cy + h / 2);
    ctx.stroke();

    // Bottom ellipse
    ctx.beginPath();
    ctx.ellipse(cx, cy + h / 2, w, ry, 0, 0, Math.PI);
    ctx.stroke();

    // Fill body
    ctx.fillStyle = 'rgba(53, 49, 72, 0.15)';
    ctx.fillRect(cx - w, cy - h / 2, w * 2, h);
}

function drawAuthIcon(ctx, s) {
    // Shield shape
    const cx = s / 2, top = s * 0.18, bottom = s * 0.82;
    const halfW = s * 0.3;
    ctx.beginPath();
    ctx.moveTo(cx, top);
    ctx.lineTo(cx + halfW, top + s * 0.12);
    ctx.lineTo(cx + halfW, s * 0.55);
    ctx.quadraticCurveTo(cx, bottom, cx, bottom);
    ctx.quadraticCurveTo(cx, bottom, cx - halfW, s * 0.55);
    ctx.lineTo(cx - halfW, top + s * 0.12);
    ctx.closePath();
    ctx.fillStyle = 'rgba(53, 49, 72, 0.2)';
    ctx.fill();
    ctx.strokeStyle = '#353148';
    ctx.stroke();
}

function drawApiIcon(ctx, s) {
    // Cloud with bidirectional arrows
    const cx = s / 2, cy = s * 0.4;
    // Simple cloud shape
    ctx.beginPath();
    ctx.arc(cx - s * 0.1, cy, s * 0.15, 0, Math.PI * 2);
    ctx.arc(cx + s * 0.1, cy, s * 0.15, 0, Math.PI * 2);
    ctx.arc(cx, cy - s * 0.08, s * 0.15, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(53, 49, 72, 0.15)';
    ctx.fill();
    ctx.strokeStyle = '#353148';
    ctx.stroke();
    // Arrows below
    const ay = s * 0.65;
    ctx.beginPath();
    ctx.moveTo(cx - s * 0.15, ay);
    ctx.lineTo(cx + s * 0.15, ay);
    ctx.moveTo(cx + s * 0.08, ay - 4);
    ctx.lineTo(cx + s * 0.15, ay);
    ctx.lineTo(cx + s * 0.08, ay + 4);
    ctx.stroke();
}

function drawUiIcon(ctx, s) {
    // Browser window
    const x = s * 0.2, y = s * 0.22, w = s * 0.6, h = s * 0.56;
    ctx.strokeRect(x, y, w, h);
    ctx.fillStyle = 'rgba(53, 49, 72, 0.1)';
    ctx.fillRect(x, y, w, h);
    // Title bar
    ctx.beginPath();
    ctx.moveTo(x, y + h * 0.2);
    ctx.lineTo(x + w, y + h * 0.2);
    ctx.stroke();
    // Dots
    const dotY = y + h * 0.1;
    for (let i = 0; i < 3; i++) {
        ctx.beginPath();
        ctx.arc(x + 6 + i * 6, dotY, 2, 0, Math.PI * 2);
        ctx.fill();
    }
}

function drawServiceIcon(ctx, s) {
    // Hexagon
    const cx = s / 2, cy = s / 2, r = s * 0.3;
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
        const angle = (Math.PI / 3) * i - Math.PI / 2;
        const px = cx + r * Math.cos(angle);
        const py = cy + r * Math.sin(angle);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.fillStyle = 'rgba(53, 49, 72, 0.15)';
    ctx.fill();
    ctx.stroke();
}

function drawConfigIcon(ctx, s) {
    // Wrench / gear simplified as a small gear
    const cx = s / 2, cy = s / 2, r = s * 0.25;
    const teeth = 6;
    ctx.beginPath();
    for (let i = 0; i < teeth * 2; i++) {
        const angle = (Math.PI / teeth) * i - Math.PI / 2;
        const tr = i % 2 === 0 ? r : r * 0.7;
        const px = cx + tr * Math.cos(angle);
        const py = cy + tr * Math.sin(angle);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.fillStyle = 'rgba(53, 49, 72, 0.2)';
    ctx.fill();
    ctx.stroke();
    // Center hole
    ctx.beginPath();
    ctx.arc(cx, cy, r * 0.25, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(248, 246, 252, 0.9)';
    ctx.fill();
}

function drawModelIcon(ctx, s) {
    // Stacked rectangles (schema)
    const cx = s / 2, w = s * 0.4, h = s * 0.12;
    for (let i = 0; i < 3; i++) {
        const y = s * 0.25 + i * (h + 4);
        ctx.strokeRect(cx - w / 2, y, w, h);
        ctx.fillStyle = 'rgba(53, 49, 72, 0.1)';
        ctx.fillRect(cx - w / 2, y, w, h);
    }
}

function drawCoreIcon(ctx, s) {
    // Diamond
    const cx = s / 2, cy = s / 2, r = s * 0.28;
    ctx.beginPath();
    ctx.moveTo(cx, cy - r);
    ctx.lineTo(cx + r, cy);
    ctx.lineTo(cx, cy + r);
    ctx.lineTo(cx - r, cy);
    ctx.closePath();
    ctx.fillStyle = 'rgba(53, 49, 72, 0.2)';
    ctx.fill();
    ctx.stroke();
}

function drawUtilIcon(ctx, s) {
    // Toolbox: rectangle with handle
    const cx = s / 2, w = s * 0.5, h = s * 0.35;
    const y = s * 0.38;
    ctx.strokeRect(cx - w / 2, y, w, h);
    ctx.fillStyle = 'rgba(53, 49, 72, 0.1)';
    ctx.fillRect(cx - w / 2, y, w, h);
    // Handle
    ctx.beginPath();
    ctx.arc(cx, y, w * 0.25, Math.PI, 0);
    ctx.stroke();
}

function drawTestIcon(ctx, s) {
    // Checkmark in a circle
    const cx = s / 2, cy = s / 2, r = s * 0.28;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(53, 49, 72, 0.1)';
    ctx.fill();
    ctx.stroke();
    // Checkmark
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(cx - r * 0.4, cy);
    ctx.lineTo(cx - r * 0.1, cy + r * 0.35);
    ctx.lineTo(cx + r * 0.4, cy - r * 0.3);
    ctx.stroke();
    ctx.lineWidth = 2;
}

/**
 * Update icon visibility to match their parent node visibility.
 */
export function updateIconVisibility(iconSprites, nodeMeshes) {
    for (const sprite of iconSprites) {
        const mesh = nodeMeshes[sprite.userData.nodeId];
        sprite.visible = mesh ? mesh.visible : false;
    }
}
```

**Step 2: Commit**

```bash
git add web/js/node-icons.js
git commit -m "feat: add node-icons.js with canvas-drawn category icons"
```

---

### Task 4: Wire semantic edges and icons into main.js

**Files:**
- Modify: `web/js/main.js:1-7` (imports)
- Modify: `web/js/main.js:62-116` (init function)

**Step 1: Add imports**

Add after line 5 (`import { createEdges } from './edges.js';`):

```javascript
import { createSemanticEdges, updateSemanticEdgeVisibility } from './semantic-edges.js';
import { createNodeIcons, updateIconVisibility } from './node-icons.js';
```

**Step 2: Wire into init()**

After the `edgeMeshes` line (line 67), add semantic edge and icon creation:

```javascript
        // Semantic edges and node icons (from optional semantic.json)
        let semanticEdgeGroups = [];
        let iconSprites = [];
        if (graph.semantic) {
            semanticEdgeGroups = createSemanticEdges(graph.semantic, nodeMeshes, scene);
            iconSprites = createNodeIcons(graph.semantic, nodeMeshes, scene);
        }
```

**Step 3: Pass semantic data to config panel for visibility updates**

Modify the `initConfigPanel` call (line 86) to pass the new mesh arrays:

```javascript
        initConfigPanel(graph, layerGroups, nodeMeshes, edgeMeshes, layerMeshes, nodeDataMap, semanticEdgeGroups, iconSprites);
```

**Step 4: Commit**

```bash
git add web/js/main.js
git commit -m "feat: wire semantic edges and node icons into main init"
```

---

### Task 5: Update config-panel.js to handle semantic edge and icon visibility

**Files:**
- Modify: `web/js/config-panel.js`

**Step 1: Update function signature and visibility logic**

Update `initConfigPanel` to accept `semanticEdgeGroups` and `iconSprites` parameters (defaulting to `[]`). In the `applyVisibility()` function, after the existing edge visibility loop, add:

```javascript
    // Update semantic edge visibility
    if (semanticEdgeGroups) {
        updateSemanticEdgeVisibility(semanticEdgeGroups, nodeMeshes);
    }
    // Update icon visibility
    if (iconSprites) {
        updateIconVisibility(iconSprites, nodeMeshes);
    }
```

Import `updateSemanticEdgeVisibility` from `./semantic-edges.js` and `updateIconVisibility` from `./node-icons.js` at the top.

**Step 2: Commit**

```bash
git add web/js/config-panel.js
git commit -m "feat: sync semantic edge and icon visibility with config toggles"
```

---

### Task 6: Add enrichment step to /prism-diff skill

**Files:**
- Modify: `commands/prism-diff.md`

**Step 1: Add enrichment step**

After step 6 (clean up worktree), before step 7 (report results), add a new step:

```markdown
7. **Enrich with semantic labels.** Read the built graph and generate `.callgraph/semantic.json`:

   Read `.callgraph/nodes.json` and `.callgraph/edges.json`. For each pair of C3 components (abstraction_level === 1) or C2 containers (abstraction_level === 2) that have edges between their children:

   - Count the underlying edges by type (calls, imports, inherits_from, depends_on)
   - Look at the function/class names involved on each side
   - Generate a 2-4 word verb phrase describing the relationship (e.g. "authenticates against", "reads data from", "orchestrates")
   - Assign each C3/C2 node a category from this fixed set: `api`, `auth`, `database`, `ui`, `config`, `util`, `core`, `test`, `model`, `service`

   Write the result as `.callgraph/semantic.json`:
   ```json
   {
     "edges": [
       {"from": "dir:src/auth", "to": "dir:src/db", "label": "validates against", "weight": 10, "types": {"calls": 8, "imports": 2}}
     ],
     "node_categories": {
       "dir:src/auth": "auth",
       "dir:src/db": "database"
     }
   }
   ```

   Use a Python snippet to aggregate the edge pairs:
   ```bash
   python3 -c "
   import json
   nodes = json.load(open('.callgraph/nodes.json'))
   edges = json.load(open('.callgraph/edges.json'))

   # Build parent chain: node -> nearest C3/C2 ancestor
   by_id = {n['id']: n for n in nodes}
   def ancestor(nid, target_levels):
       visited = set()
       cur = nid
       while cur and cur not in visited:
           node = by_id.get(cur)
           if not node: break
           if node.get('abstraction_level') in target_levels:
               return cur
           visited.add(cur)
           cur = node.get('parent')
       return None

   # Aggregate edges between C3 pairs
   pairs = {}
   for e in edges:
       if e['type'] == 'contains': continue
       a = ancestor(e['from'], {1, 2})
       b = ancestor(e['to'], {1, 2})
       if not a or not b or a == b: continue
       key = (a, b)
       if key not in pairs: pairs[key] = {}
       t = e['type']
       pairs[key][t] = pairs[key].get(t, 0) + 1

   result = []
   for (a, b), types in pairs.items():
       weight = sum(types.values())
       result.append({'from': a, 'to': b, 'weight': weight, 'types': types})

   print(json.dumps(result, indent=2))
   "
   ```

   Use the aggregated pairs output to generate semantic labels. For each pair, based on the component names, edge types, and weights, write a 2-4 word verb phrase as the `label`. Also assign each unique node ID a category. Write the complete `semantic.json`.
```

Renumber subsequent steps accordingly.

**Step 2: Commit**

```bash
git add commands/prism-diff.md
git commit -m "feat: add semantic enrichment step to /prism-diff skill"
```

---

### Task 7: Add enrichment step to /prism-impact skill

**Files:**
- Modify: `commands/prism-impact.md`

**Step 1: Add the same enrichment step**

After step 5 (apply the plan), before step 6 (report results), add the identical semantic enrichment step as in Task 6. Copy the same instructions and Python snippet.

Renumber subsequent steps accordingly.

**Step 2: Commit**

```bash
git add commands/prism-impact.md
git commit -m "feat: add semantic enrichment step to /prism-impact skill"
```

---

### Task 8: Manual integration test with sample semantic.json

**Files:**
- Create (temporary): `.callgraph/semantic.json` (test data)

**Step 1: Create test semantic.json**

To test the viewer without running a full enrichment, create a sample `.callgraph/semantic.json` with data matching the current graph's node IDs. First inspect nodes to find valid C3/C2 IDs:

```bash
python3 -c "
import json
nodes = json.load(open('.callgraph/nodes.json'))
for n in nodes:
    if n.get('abstraction_level') in (1, 2):
        print(n['id'], n.get('name'), 'level=' + str(n['abstraction_level']))
"
```

Then write a `semantic.json` using 2-3 real node IDs from the output, with test labels and categories.

**Step 2: Run viewer and verify**

```bash
callgraph serve
```

Verify:
- Circuit-style arrows appear between C3/C2 nodes
- Text labels are readable and billboard-facing
- Icon sprites appear above categorized nodes
- Toggling layers hides/shows the semantic edges and icons
- No console errors
- Viewer still works if `semantic.json` is deleted (fallback)

**Step 3: Clean up test data and commit**

Remove the test `semantic.json` if it was only for testing. Final commit:

```bash
git commit -m "feat: semantic edges and node icons integration complete"
```
