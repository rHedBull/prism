# 2D Semantic Zoom Viewing Mode — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a 2D semantic zoom viewing mode with nested treemap layout and smooth zoom-based layer transitions.

**Architecture:** New `mode-2d.js` module handles orthographic camera, pan/zoom controls, and semantic zoom logic. New `layout-treemap.js` builds a nested squarified treemap for all 4 layers at Y=0. Existing modules (interaction, edges, diff) get minimal changes to work with both modes. A global `window._viewMode` flag ('2d'|'3d') coordinates behavior.

**Tech Stack:** Three.js (OrthographicCamera, PlaneGeometry), existing squarified treemap algorithm from layers.js (extracted and extended), TWEEN for animations.

---

### Task 1: Add 2D/3D toggle button to HTML

**Files:**
- Modify: `web/index.html:380-383`

**Step 1: Add the toggle button**

Add a `btn-toggle-2d` button to the `#controls` div, right after the reset button:

```html
<div id="controls">
    <button id="btn-reset">Reset View</button>
    <button id="btn-toggle-2d">2D View</button>
    <button id="btn-toggle-diff" style="display:none;">Show Diff</button>
</div>
```

**Step 2: Verify**

Open `web/index.html` in browser, confirm the "2D View" button appears in the bottom controls bar.

**Step 3: Commit**

```bash
git add web/index.html
git commit -m "feat: add 2D/3D toggle button to controls bar"
```

---

### Task 2: Create nested treemap layout module

**Files:**
- Create: `web/js/layout-treemap.js`

This module takes the `layerGroups` data (from `graph-loader.js`) and computes a nested treemap where C1 boxes contain C2 boxes, C2 contain C3, C3 contain C4.

**Step 1: Create `layout-treemap.js`**

```javascript
/**
 * Nested squarified treemap layout for 2D mode.
 * Computes { x, z, w, d } rectangles for every node across all layers,
 * with children nested inside their parent's rectangle.
 */

const NEST_PADDING = 1.5;  // padding inside parent rect for children
const LABEL_RESERVE = 1.0; // space at top of parent for label

/**
 * Squarified treemap: lay out items into near-square rectangles.
 * items: [{ id, area }] sorted by area descending.
 * Returns [{ id, x, z, w, d }] — positions within the given (x, z, w, d) rect.
 */
function squarify(items, x, z, w, d) {
    if (items.length === 0) return [];
    if (items.length === 1) {
        return [{ id: items[0].id, x, z, w, d }];
    }

    const totalArea = items.reduce((s, e) => s + e.area, 0);
    const horizontal = w >= d;
    const sideLen = horizontal ? d : w;

    // Greedily fill a strip until aspect ratio worsens
    let bestRow = [items[0]];
    let bestWorst = Infinity;

    for (let i = 1; i <= items.length; i++) {
        const row = items.slice(0, i);
        const rowArea = row.reduce((s, e) => s + e.area, 0);
        const stripLen = rowArea / sideLen;

        let worstAR = 0;
        for (const item of row) {
            const itemSide = item.area / stripLen;
            const ar = Math.max(stripLen / itemSide, itemSide / stripLen);
            worstAR = Math.max(worstAR, ar);
        }

        if (worstAR <= bestWorst) {
            bestWorst = worstAR;
            bestRow = row;
        } else {
            break;
        }
    }

    const rects = [];
    const rowArea = bestRow.reduce((s, e) => s + e.area, 0);
    const stripLen = rowArea / sideLen;
    let offset = 0;

    for (const item of bestRow) {
        const itemSide = item.area / stripLen;
        if (horizontal) {
            rects.push({ id: item.id, x, z: z + offset, w: stripLen, d: itemSide });
        } else {
            rects.push({ id: item.id, x: x + offset, z, w: itemSide, d: stripLen });
        }
        offset += itemSide;
    }

    // Recurse on remaining items
    const rest = items.slice(bestRow.length);
    if (rest.length > 0) {
        let childRects;
        if (horizontal) {
            childRects = squarify(rest, x + stripLen, z, w - stripLen, d);
        } else {
            childRects = squarify(rest, x, z + stripLen, w, d - stripLen);
        }
        rects.push(...childRects);
    }

    return rects;
}

/**
 * Build a nested treemap layout for all layers.
 *
 * @param {Object} layerGroups — { 3: [C1 nodes], 2: [C2], 1: [C3], 0: [C4] }
 * @param {number} totalW — total width of the treemap
 * @param {number} totalD — total depth of the treemap
 * @returns {Map<string, {x, z, w, d, level}>} — nodeId -> rectangle
 */
export function buildNestedTreemap(layerGroups, totalW, totalD) {
    const layout = new Map(); // nodeId -> { x, z, w, d, level }

    // Start with C1 nodes filling the entire area
    const c1Nodes = layerGroups[3] || [];
    if (c1Nodes.length === 0) return layout;

    const c1Items = c1Nodes.map(n => ({
        id: n.id,
        area: Math.max(1, n.lines_of_code || n.child_count || 1),
    })).sort((a, b) => b.area - a.area);

    const c1Rects = squarify(c1Items, 0, 0, totalW, totalD);
    for (const r of c1Rects) {
        layout.set(r.id, { x: r.x, z: r.z, w: r.w, d: r.d, level: 3 });
    }

    // For each deeper level, nest children inside their parent's rect
    const levels = [
        { parent: 3, child: 2 },
        { parent: 2, child: 1 },
        { parent: 1, child: 0 },
    ];

    for (const { parent: parentLevel, child: childLevel } of levels) {
        const childNodes = layerGroups[childLevel] || [];
        if (childNodes.length === 0) continue;

        // Group children by their _layerParent
        const groups = {};
        for (const node of childNodes) {
            const pid = node._layerParent || '_orphan';
            if (!groups[pid]) groups[pid] = [];
            groups[pid].push(node);
        }

        for (const [parentId, children] of Object.entries(groups)) {
            const parentRect = layout.get(parentId);
            if (!parentRect) {
                // Orphan nodes — place in a fallback area
                continue;
            }

            // Inner rect with padding and label reserve
            const innerX = parentRect.x + NEST_PADDING;
            const innerZ = parentRect.z + NEST_PADDING + LABEL_RESERVE;
            const innerW = Math.max(1, parentRect.w - NEST_PADDING * 2);
            const innerD = Math.max(1, parentRect.d - NEST_PADDING * 2 - LABEL_RESERVE);

            const items = children.map(n => ({
                id: n.id,
                area: Math.max(1, n.lines_of_code || n.child_count || 1),
            })).sort((a, b) => b.area - a.area);

            const rects = squarify(items, innerX, innerZ, innerW, innerD);
            for (const r of rects) {
                layout.set(r.id, { x: r.x, z: r.z, w: r.w, d: r.d, level: childLevel });
            }
        }
    }

    return layout;
}
```

**Step 2: Verify**

No tests for this project, but verify the file loads without syntax errors by importing it in the browser console.

**Step 3: Commit**

```bash
git add web/js/layout-treemap.js
git commit -m "feat: add nested squarified treemap layout for 2D mode"
```

---

### Task 3: Create 2D mode module (camera, controls, zoom)

**Files:**
- Create: `web/js/mode-2d.js`

**Step 1: Create `mode-2d.js`**

This module manages:
- Orthographic camera creation and frustum sizing
- Pan (right-drag) and zoom (scroll) controls
- Semantic zoom: determine which layers to show based on frustum size
- Building 2D meshes from the nested treemap layout

```javascript
/**
 * 2D semantic zoom mode.
 * Orthographic top-down camera with nested treemap layout.
 */
import * as THREE from 'three';
import * as TWEEN from '@tweenjs/tween.js';
import { buildNestedTreemap } from './layout-treemap.js';
import { computeColor, computeMetricRange } from './metrics.js';
import { requestRender, getCanvasWidth } from './scene.js';

const LAYER_COLORS = {
    0: 0x4A90D9, 1: 0x8c60f3, 2: 0x2ECC71, 3: 0xE74C3C,
};

const LAYER_LABELS = {
    0: 'C4', 1: 'C3', 2: 'C2', 3: 'C1',
};

// Zoom thresholds: frustum half-width at which each layer becomes visible
// Smaller frustum = more zoomed in
const ZOOM_THRESHOLDS = {
    3: Infinity,  // C1 always visible
    2: 60,        // C2 appears when frustum < 60
    1: 30,        // C3 appears when frustum < 30
    0: 15,        // C4 appears when frustum < 15
};

// Frustum range where a layer transitions from container to hidden
const FADE_RANGE = 5; // units of frustum half-width for opacity transition

let _camera2d = null;
let _meshGroup = null;   // THREE.Group holding all 2D meshes
let _treemapLayout = null;
let _nodeMeshes2d = {};  // nodeId -> mesh
let _containerMeshes = {}; // nodeId -> container outline mesh
let _labelSprites = {};  // nodeId -> label sprite
let _layerGroups = null;
let _nodeDataMap2d = new Map();
let _totalSize = 80;
let _isPanning = false;
let _panStart = { x: 0, y: 0 };
let _cameraStart = { x: 0, z: 0 };

export function create2DCamera() {
    const aspect = getCanvasWidth() / window.innerHeight;
    const frustumHalf = _totalSize * 0.6;
    _camera2d = new THREE.OrthographicCamera(
        -frustumHalf * aspect, frustumHalf * aspect,
        frustumHalf, -frustumHalf,
        0.1, 100
    );
    _camera2d.position.set(_totalSize / 2, 50, _totalSize / 2);
    _camera2d.lookAt(_totalSize / 2, 0, _totalSize / 2);
    _camera2d.up.set(0, 0, -1); // so X goes right, Z goes down
    return _camera2d;
}

export function get2DCamera() { return _camera2d; }
export function get2DNodeMeshes() { return _nodeMeshes2d; }
export function get2DNodeDataMap() { return _nodeDataMap2d; }

/**
 * Build all 2D meshes from layerGroups data.
 * Returns { meshGroup, nodeMeshes2d, nodeDataMap2d }
 */
export function build2DScene(layerGroups, scene) {
    _layerGroups = layerGroups;

    // Clean up previous 2D scene
    if (_meshGroup) {
        scene.remove(_meshGroup);
        _meshGroup.traverse(child => {
            if (child.geometry) child.geometry.dispose();
            if (child.material) {
                if (child.material.map) child.material.map.dispose();
                child.material.dispose();
            }
        });
    }

    _meshGroup = new THREE.Group();
    _nodeMeshes2d = {};
    _containerMeshes = {};
    _labelSprites = {};
    _nodeDataMap2d = new Map();

    // Determine total size based on node count
    const allNodes = Object.values(layerGroups).flat();
    const totalNodes = allNodes.length;
    _totalSize = Math.max(60, Math.sqrt(totalNodes) * 8);

    // Build nested layout
    _treemapLayout = buildNestedTreemap(layerGroups, _totalSize, _totalSize);

    // Compute colors
    const metricRange = computeMetricRange(allNodes);

    // Create meshes for each node
    for (const [nodeId, rect] of _treemapLayout) {
        const node = allNodes.find(n => n.id === nodeId);
        if (!node) continue;

        const level = rect.level;

        // Filled rectangle (the node box)
        const color = computeColor(node, metricRange);
        const geo = new THREE.PlaneGeometry(rect.w, rect.d);
        const mat = new THREE.MeshBasicMaterial({
            color,
            transparent: true,
            opacity: 1.0,
            side: THREE.DoubleSide,
        });
        const mesh = new THREE.Mesh(geo, mat);
        // Plane lies in XZ — rotate to horizontal, position at Y=0
        mesh.rotation.x = -Math.PI / 2;
        mesh.position.set(rect.x + rect.w / 2, level * 0.01, rect.z + rect.d / 2);
        mesh.userData = { type: 'node', nodeData: node, _origColor: color, _rect: rect };
        _meshGroup.add(mesh);
        _nodeMeshes2d[nodeId] = mesh;
        _nodeDataMap2d.set(mesh, node);

        // Container outline (border) — for parent nodes when zoomed in
        const edgesGeo = new THREE.EdgesGeometry(geo);
        const edgesMat = new THREE.LineBasicMaterial({
            color: LAYER_COLORS[level] || 0x666666,
            transparent: true,
            opacity: 0.6,
        });
        const outline = new THREE.LineSegments(edgesGeo, edgesMat);
        outline.rotation.x = -Math.PI / 2;
        outline.position.set(rect.x + rect.w / 2, level * 0.01 + 0.005, rect.z + rect.d / 2);
        _meshGroup.add(outline);
        _containerMeshes[nodeId] = outline;

        // Label sprite
        const label = _createLabel(node.name, LAYER_COLORS[level] || 0x666666);
        label.position.set(rect.x + rect.w / 2, level * 0.01 + 0.02, rect.z + 0.8);
        const labelScale = Math.min(rect.w * 0.8, 8);
        label.scale.set(labelScale, labelScale * 0.15, 1);
        _meshGroup.add(label);
        _labelSprites[nodeId] = label;
    }

    scene.add(_meshGroup);

    // Reset camera to fit
    if (_camera2d) {
        const aspect = getCanvasWidth() / window.innerHeight;
        const frustumHalf = _totalSize * 0.6;
        _camera2d.left = -frustumHalf * aspect;
        _camera2d.right = frustumHalf * aspect;
        _camera2d.top = frustumHalf;
        _camera2d.bottom = -frustumHalf;
        _camera2d.position.set(_totalSize / 2, 50, _totalSize / 2);
        _camera2d.lookAt(_totalSize / 2, 0, _totalSize / 2);
        _camera2d.updateProjectionMatrix();
    }

    // Apply initial semantic zoom
    updateSemanticZoom();

    return { meshGroup: _meshGroup, nodeMeshes2d: _nodeMeshes2d, nodeDataMap2d: _nodeDataMap2d };
}

/**
 * Update visibility and opacity of nodes based on current zoom level.
 */
export function updateSemanticZoom() {
    if (!_camera2d || !_treemapLayout) return;

    const frustumHalf = (_camera2d.right - _camera2d.left) / 2;

    for (const [nodeId, rect] of _treemapLayout) {
        const mesh = _nodeMeshes2d[nodeId];
        const outline = _containerMeshes[nodeId];
        const label = _labelSprites[nodeId];
        if (!mesh) continue;

        const level = rect.level;
        const threshold = ZOOM_THRESHOLDS[level];

        // Is this level visible at current zoom?
        const visible = frustumHalf <= threshold;

        // Is there a deeper level that's also visible? If so, this becomes a container.
        const deeperLevel = level - 1;
        const deeperThreshold = ZOOM_THRESHOLDS[deeperLevel];
        const deeperVisible = deeperLevel >= 0 && frustumHalf <= deeperThreshold;

        if (!visible) {
            mesh.visible = false;
            if (outline) outline.visible = false;
            if (label) label.visible = false;
            continue;
        }

        mesh.visible = true;

        if (deeperVisible) {
            // This node is a container — show as outline only
            mesh.material.opacity = 0.08;
            if (outline) {
                outline.visible = true;
                outline.material.opacity = 0.5;
            }
            if (label) {
                label.visible = true;
                label.material.opacity = 0.7;
            }
        } else {
            // This node is a leaf at current zoom — show filled
            // Compute fade-in based on distance from threshold
            const fadeStart = threshold;
            const fadeEnd = threshold - FADE_RANGE;
            let opacity = 1.0;
            if (frustumHalf > fadeEnd && frustumHalf <= fadeStart) {
                opacity = 1.0 - (frustumHalf - fadeEnd) / FADE_RANGE;
            }
            mesh.material.opacity = Math.max(0.3, opacity);
            if (outline) {
                outline.visible = true;
                outline.material.opacity = 0.8;
            }
            if (label) {
                label.visible = true;
                label.material.opacity = opacity;
            }
        }
    }
}

/**
 * Handle scroll zoom for 2D mode.
 */
export function setup2DControls(renderer) {
    const canvas = renderer.domElement;

    canvas.addEventListener('wheel', (e) => {
        if (!_camera2d || window._viewMode !== '2d') return;
        e.preventDefault();

        const zoomFactor = e.deltaY > 0 ? 1.1 : 0.9;
        const aspect = getCanvasWidth() / window.innerHeight;

        // Get world position under mouse before zoom
        const rect = canvas.getBoundingClientRect();
        const mx = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        const my = -((e.clientY - rect.top) / rect.height) * 2 + 1;

        const halfW = (_camera2d.right - _camera2d.left) / 2;
        const halfH = (_camera2d.top - _camera2d.bottom) / 2;
        const worldX = _camera2d.position.x + mx * halfW;
        const worldZ = _camera2d.position.z - my * halfH;

        // Apply zoom
        const newHalfW = halfW * zoomFactor;
        const minZoom = 3;
        const maxZoom = _totalSize * 1.2;
        const clampedHalf = Math.max(minZoom, Math.min(maxZoom, newHalfW));

        _camera2d.left = -clampedHalf * aspect;
        _camera2d.right = clampedHalf * aspect;
        _camera2d.top = clampedHalf;
        _camera2d.bottom = -clampedHalf;

        // Adjust camera position to zoom toward mouse
        const newHalf = clampedHalf;
        const scale = newHalf / halfW;
        _camera2d.position.x = worldX - mx * newHalf;
        _camera2d.position.z = worldZ + my * newHalf;

        _camera2d.updateProjectionMatrix();
        updateSemanticZoom();
        requestRender();
    }, { passive: false });

    // Pan with right-click drag or middle-click drag
    canvas.addEventListener('mousedown', (e) => {
        if (!_camera2d || window._viewMode !== '2d') return;
        if (e.button === 2 || e.button === 1) {
            _isPanning = true;
            _panStart = { x: e.clientX, y: e.clientY };
            _cameraStart = { x: _camera2d.position.x, z: _camera2d.position.z };
            e.preventDefault();
        }
    });

    window.addEventListener('mousemove', (e) => {
        if (!_isPanning || !_camera2d || window._viewMode !== '2d') return;
        const dx = e.clientX - _panStart.x;
        const dy = e.clientY - _panStart.y;

        const frustumW = _camera2d.right - _camera2d.left;
        const frustumH = _camera2d.top - _camera2d.bottom;
        const canvasW = getCanvasWidth();
        const canvasH = window.innerHeight;

        _camera2d.position.x = _cameraStart.x - (dx / canvasW) * frustumW;
        _camera2d.position.z = _cameraStart.z + (dy / canvasH) * frustumH;
        _camera2d.updateProjectionMatrix();
        requestRender();
    });

    window.addEventListener('mouseup', (e) => {
        if (e.button === 2 || e.button === 1) {
            _isPanning = false;
        }
    });

    // Prevent context menu on right-click for panning
    canvas.addEventListener('contextmenu', (e) => {
        if (window._viewMode === '2d') e.preventDefault();
    });
}

/**
 * Animate zoom into a specific node (for click-to-drill).
 */
export function zoomToNode(nodeId) {
    if (!_camera2d || !_treemapLayout) return;
    const rect = _treemapLayout.get(nodeId);
    if (!rect) return;

    const aspect = getCanvasWidth() / window.innerHeight;
    const targetHalf = Math.max(rect.w, rect.d) * 0.8;
    const targetX = rect.x + rect.w / 2;
    const targetZ = rect.z + rect.d / 2;

    const startLeft = _camera2d.left;
    const startRight = _camera2d.right;
    const startTop = _camera2d.top;
    const startBottom = _camera2d.bottom;
    const startX = _camera2d.position.x;
    const startZ = _camera2d.position.z;

    new TWEEN.Tween({ t: 0 })
        .to({ t: 1 }, 600)
        .easing(TWEEN.Easing.Cubic.InOut)
        .onUpdate(({ t }) => {
            const half = startTop + (targetHalf - startTop) * t;
            _camera2d.left = -half * aspect;
            _camera2d.right = half * aspect;
            _camera2d.top = half;
            _camera2d.bottom = -half;
            _camera2d.position.x = startX + (targetX - startX) * t;
            _camera2d.position.z = startZ + (targetZ - startZ) * t;
            _camera2d.updateProjectionMatrix();
            updateSemanticZoom();
            requestRender();
        })
        .start();
    requestRender();
}

/**
 * Clean up 2D scene meshes.
 */
export function destroy2DScene(scene) {
    if (_meshGroup) {
        scene.remove(_meshGroup);
        _meshGroup.traverse(child => {
            if (child.geometry) child.geometry.dispose();
            if (child.material) {
                if (child.material.map) child.material.map.dispose();
                child.material.dispose();
            }
        });
        _meshGroup = null;
    }
    _nodeMeshes2d = {};
    _containerMeshes = {};
    _labelSprites = {};
    _nodeDataMap2d = new Map();
    _treemapLayout = null;
}

export function resize2DCamera() {
    if (!_camera2d) return;
    const aspect = getCanvasWidth() / window.innerHeight;
    const halfH = (_camera2d.top - _camera2d.bottom) / 2;
    _camera2d.left = -halfH * aspect;
    _camera2d.right = halfH * aspect;
    _camera2d.updateProjectionMatrix();
}

function _createLabel(text, color) {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.font = 'bold 28px monospace';
    ctx.fillStyle = `#${new THREE.Color(color).getHexString()}`;
    ctx.fillText(text, 10, 44);

    const texture = new THREE.CanvasTexture(canvas);
    texture.premultiplyAlpha = true;
    const mat = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false });
    const sprite = new THREE.Sprite(mat);
    return sprite;
}
```

**Step 2: Verify**

Check file loads without syntax errors in browser console.

**Step 3: Commit**

```bash
git add web/js/mode-2d.js
git commit -m "feat: add 2D mode module with orthographic camera and semantic zoom"
```

---

### Task 4: Wire up mode toggle in main.js

**Files:**
- Modify: `web/js/main.js`

**Step 1: Add imports and mode toggle logic**

At the top of `main.js`, add the import:
```javascript
import { create2DCamera, build2DScene, destroy2DScene, setup2DControls, resize2DCamera, get2DCamera, get2DNodeMeshes, get2DNodeDataMap, updateSemanticZoom } from './mode-2d.js';
```

Set `window._viewMode = '3d'` after scene creation.

In `init()`, after the existing setup, add mode toggle wiring:

```javascript
// Store references for mode switching
const state3d = { layerMeshes, nodeMeshes, edgeMeshes, nodeDataMap };
let state2d = null;

// Create 2D camera and controls
const camera2d = create2DCamera();
setup2DControls(renderer);

// Mode toggle
const toggleBtn = document.getElementById('btn-toggle-2d');
toggleBtn.addEventListener('click', () => {
    if (window._viewMode === '3d') {
        // Switch to 2D
        window._viewMode = '2d';
        toggleBtn.textContent = '3D View';

        // Hide 3D objects
        for (const [level, group] of Object.entries(layerMeshes)) group.visible = false;
        for (const mesh of Object.values(nodeMeshes)) mesh.visible = false;
        for (const line of edgeMeshes) line.visible = false;

        // Build 2D scene
        state2d = build2DScene(layerGroups, scene);

        // Switch camera & disable orbit controls
        controls.enabled = false;

        // Re-setup interaction for 2D
        requestRender();
    } else {
        // Switch to 3D
        window._viewMode = '3d';
        toggleBtn.textContent = '2D View';

        // Destroy 2D scene
        destroy2DScene(scene);

        // Restore 3D objects
        for (const [level, group] of Object.entries(layerMeshes)) group.visible = true;
        for (const [id, mesh] of Object.entries(nodeMeshes)) mesh.visible = true;
        for (const line of edgeMeshes) line.visible = true;

        // Re-enable orbit controls
        controls.enabled = true;

        requestRender();
    }
});
```

**Step 2: Update the render loop in `scene.js`**

In `initRenderer`, the render callback needs to use the right camera:

```javascript
render: () => {
    TWEEN.update();
    const cam = window._viewMode === '2d' ? get2DCamera() : camera;
    if (cam) renderer.render(scene, cam);
},
```

This requires importing `get2DCamera` in `scene.js` — but to avoid circular deps, instead pass the camera resolver into `initRenderer`. Alternative: use `window._activeCamera`.

Simpler approach: set `window._activeCamera = camera` in main.js, update it on mode switch, and use it in the render loop.

**Step 3: Update `resizeCanvas` to handle 2D camera**

In the resize handler, also call `resize2DCamera()` when in 2D mode.

**Step 4: Verify**

Open browser. Click "2D View" button. Should see the nested treemap. Click "3D View" to go back. Scroll to zoom in 2D and see layers appear.

**Step 5: Commit**

```bash
git add web/js/main.js web/js/scene.js
git commit -m "feat: wire up 2D/3D mode toggle with camera switching"
```

---

### Task 5: Update interaction.js for 2D mode

**Files:**
- Modify: `web/js/interaction.js`

**Step 1: Make raycasting use the active camera**

The interaction module references `camera` from the closure. Update the mousemove and click handlers to use `window._activeCamera` (set by main.js) instead of the closure `camera` variable. This way raycasting works in both modes.

**Step 2: Use mode-appropriate meshes for raycasting**

When in 2D mode, raycast against 2D meshes. When in 3D, raycast against 3D meshes:

```javascript
// In mousemove handler:
const activeMeshes = window._viewMode === '2d'
    ? Array.from(get2DNodeDataMap().keys())
    : _raycastMeshes;
const activeDataMap = window._viewMode === '2d'
    ? get2DNodeDataMap()
    : nodeDataMap;
```

**Step 3: Double-click in 2D mode zooms into container**

When double-clicking a node in 2D mode, if it has children, call `zoomToNode(data.id)` to smoothly zoom in:

```javascript
// In dblclick handler, add 2D zoom behavior:
if (window._viewMode === '2d') {
    zoomToNode(data.id);
    return;
}
```

**Step 4: Verify**

Hover over nodes in 2D mode — info panel should appear. Double-click a container to zoom in.

**Step 5: Commit**

```bash
git add web/js/interaction.js
git commit -m "feat: update interaction handling for 2D mode raycasting and zoom"
```

---

### Task 6: Handle edges in 2D mode

**Files:**
- Modify: `web/js/edges.js`

**Step 1: Create 2D edge rendering**

When edges need to be shown (hover/selection), draw them as flat 2D bezier curves at Y=0.1 between node centers. Since edges are only shown on hover in 2D mode, this can reuse the existing edge highlight logic but with adjusted midpoint calculation (no vertical offset, just horizontal arc):

```javascript
// In createEdges or a new createEdges2D function:
// For 2D mode, mid.y stays at 0.1, and the arc is in XZ plane
if (window._viewMode === '2d') {
    const dx = end.x - start.x;
    const dz = end.z - start.z;
    mid.y = 0.1;
    mid.x = (start.x + end.x) / 2 + dz * 0.15;
    mid.z = (start.z + end.z) / 2 - dx * 0.15;
}
```

Since edges are hidden by default in 2D, set all edge meshes to `visible = false` when switching to 2D, and only show relevant ones on hover (which the existing `highlightEdges` already handles via opacity).

**Step 2: Verify**

Hover a node in 2D mode — connected edges should appear as curved lines.

**Step 3: Commit**

```bash
git add web/js/edges.js
git commit -m "feat: adjust edge rendering for 2D mode"
```

---

### Task 7: Update config panel for 2D mode

**Files:**
- Modify: `web/js/config-panel.js`

**Step 1: Hide layer checkboxes in 2D mode**

The layer visibility checkboxes don't make sense in 2D mode (zoom controls visibility). Hide the "Layers" section when in 2D:

```javascript
// After mode toggle, update config panel
const layersSection = document.querySelector('.config-section:has(#layer-3)')
    || document.getElementById('layer-3')?.closest('.config-section');
if (layersSection) {
    layersSection.style.display = window._viewMode === '2d' ? 'none' : '';
}
```

This can be wired from main.js after the mode toggle click handler.

**Step 2: Verify**

Toggle to 2D mode — Layers section should disappear from config panel. Toggle back — it reappears.

**Step 3: Commit**

```bash
git add web/js/config-panel.js web/js/main.js
git commit -m "feat: hide layer toggles in 2D mode"
```

---

### Task 8: Integration testing and polish

**Files:**
- Modify: Various (polish pass)

**Step 1: Test the full flow**

1. Load viewer — should start in 3D mode
2. Click "2D View" — nested treemap appears, C1 boxes visible
3. Scroll zoom in — C2 boxes appear inside C1 containers, C1 fades to outline
4. Keep zooming — C3, then C4 appear
5. Hover a node — info panel, edges appear
6. Double-click a container — smooth zoom animation
7. Right-click drag — pan
8. Press Escape or click "3D View" — back to 3D
9. Toggle diff mode in both 2D and 3D

**Step 2: Tune zoom thresholds**

Adjust `ZOOM_THRESHOLDS` in `mode-2d.js` based on actual data — the right values depend on typical node counts and treemap size. May need to make these dynamic based on `_totalSize`.

**Step 3: Fix any visual issues**

- Labels not readable at certain zoom levels → adjust scale
- Containers too faint or too strong → adjust opacity values
- Pan feels too fast/slow → adjust multiplier

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: polish 2D semantic zoom mode"
```
