# Metric-Driven Block Size & Color Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users choose which metric drives block height and block color via dropdowns in the config panel. Default size metric is "complexity" which auto-selects the right metric per C-level.

**Architecture:** A new `metrics.js` module computes derived metrics (fan_in, fan_out, child_count) at load time and provides functions to map any metric to height or color. The "complexity" size mode picks lines_of_code for C4, child_count for C3/C2/C1. `layers.js` reads the active metric when creating blocks. `config-panel.js` adds two dropdowns and re-renders blocks when they change. The info panel shows the active metric value.

**Tech Stack:** JavaScript (Three.js), HTML/CSS

---

### Task 1: Create `metrics.js` — derived metric computation and mapping functions

**Files:**
- Create: `web/js/metrics.js`

**Step 1: Create the metrics module**

```javascript
// web/js/metrics.js
import * as THREE from 'three';

const LOC_SCALE = 0.08;

// Available metrics for size and color dropdowns
export const SIZE_METRICS = ['complexity', 'lines_of_code', 'export_count', 'fan_in', 'fan_out', 'child_count'];
export const COLOR_METRICS = ['language', 'lines_of_code', 'export_count', 'fan_in', 'fan_out', 'child_count'];

const LANGUAGE_COLORS = {
    python: 0x8c60f3,
    typescript: 0x6a3fd4,
    typescriptreact: 0x6a3fd4,
    javascript: 0xb89ef7,
    javascriptreact: 0xb89ef7,
};

// Current selections (module-level state)
let _sizeMetric = 'complexity';
let _colorMetric = 'language';

export function getSizeMetric() { return _sizeMetric; }
export function getColorMetric() { return _colorMetric; }
export function setSizeMetric(m) { _sizeMetric = m; }
export function setColorMetric(m) { _colorMetric = m; }

/**
 * Resolve the effective metric for a node's size.
 * "complexity" picks the right metric per abstraction level:
 *   C4 (level 0) = lines_of_code (function size)
 *   C3 (level 1) = child_count (number of files)
 *   C2 (level 2) = child_count (number of components)
 *   C1 (level 3) = child_count (number of containers)
 */
function resolveSizeMetric(node) {
    if (_sizeMetric !== 'complexity') return _sizeMetric;
    const level = node.abstraction_level ?? 0;
    return level === 0 ? 'lines_of_code' : 'child_count';
}

/**
 * Compute derived metrics (fan_in, fan_out, child_count) and attach to each node.
 * Call once after graph load, before createLayers.
 */
export function computeDerivedMetrics(nodes, edges) {
    const fanIn = {};
    const fanOut = {};
    const childCount = {};

    // Count edges
    for (const edge of edges) {
        fanOut[edge.from] = (fanOut[edge.from] || 0) + 1;
        fanIn[edge.to] = (fanIn[edge.to] || 0) + 1;
    }

    // Count children (by _layerParent or parent)
    for (const node of nodes) {
        const pid = node._layerParent || node.parent;
        if (pid) {
            childCount[pid] = (childCount[pid] || 0) + 1;
        }
    }

    // Attach to nodes
    for (const node of nodes) {
        node.fan_in = fanIn[node.id] || 0;
        node.fan_out = fanOut[node.id] || 0;
        node.child_count = childCount[node.id] || 0;
    }
}

/**
 * Compute block height from the active size metric.
 */
export function computeHeight(node) {
    const metric = resolveSizeMetric(node);
    const value = node[metric] || 0;
    return Math.max(0.8, Math.log2(Math.max(1, value)) * LOC_SCALE * 8);
}

/**
 * Return the effective size metric name and value for a node (for info panel).
 */
export function getSizeInfo(node) {
    const metric = resolveSizeMetric(node);
    return { metric, value: node[metric] ?? 0 };
}

/**
 * Compute block color from the active color metric.
 * For 'language': returns categorical color.
 * For numeric metrics: returns sequential gradient blue->red.
 */
export function computeColor(node, metricRange) {
    if (_colorMetric === 'language') {
        return LANGUAGE_COLORS[node.language] || 0x888888;
    }

    const value = node[_colorMetric] || 0;
    const { min, max } = metricRange;
    const t = max > min ? (value - min) / (max - min) : 0;

    // Sequential gradient: blue (0x4A90D9) -> red (0xE74C3C) via HSL
    const lowColor = new THREE.Color(0x4A90D9);
    const highColor = new THREE.Color(0xE74C3C);
    const hslLow = {}; lowColor.getHSL(hslLow);
    const hslHigh = {}; highColor.getHSL(hslHigh);

    const c = new THREE.Color();
    c.setHSL(
        hslLow.h + (hslHigh.h - hslLow.h) * t,
        hslLow.s + (hslHigh.s - hslLow.s) * t,
        hslLow.l + (hslHigh.l - hslLow.l) * t,
    );
    return c.getHex();
}

/**
 * Compute min/max of the active color metric across a flat list of nodes.
 */
export function computeMetricRange(allNodes) {
    if (_colorMetric === 'language') return { min: 0, max: 1 };
    let min = Infinity, max = -Infinity;
    for (const node of allNodes) {
        const v = node[_colorMetric] || 0;
        if (v < min) min = v;
        if (v > max) max = v;
    }
    if (min === Infinity) { min = 0; max = 1; }
    return { min, max };
}
```

**Step 2: Verify the file loads without errors**

Open browser dev console, check no import errors. (File is not imported yet — just validate syntax.)

**Step 3: Commit**

```bash
git add web/js/metrics.js
git commit -m "feat: add metrics.js with complexity-aware size and color mapping"
```

---

### Task 2: Wire `metrics.js` into `graph-loader.js` and `layers.js`

**Files:**
- Modify: `web/js/graph-loader.js`
- Modify: `web/js/layers.js`
- Modify: `web/js/main.js`

**Step 1: Call computeDerivedMetrics in graph-loader.js**

In `web/js/graph-loader.js`, add the import at the top:

```javascript
import { computeDerivedMetrics } from './metrics.js';
```

Change the function signature to accept edges:

```javascript
export function groupByAbstractionLevel(nodes, edges = []) {
```

At the end of `groupByAbstractionLevel`, before `return layers`, add:

```javascript
    // Compute derived metrics on all layer nodes
    const allNodes = Object.values(layers).flat();
    computeDerivedMetrics(allNodes, edges);
```

In `web/js/main.js`, update the call:

```javascript
const layerGroups = groupByAbstractionLevel(graph.nodes, graph.edges);
```

**Step 2: Use metrics.js in layers.js for height and color**

In `web/js/layers.js`:

Remove `LANGUAGE_COLORS` and `LOC_SCALE` constants (they now live in metrics.js).

Add import at top:

```javascript
import { computeHeight, computeColor, computeMetricRange } from './metrics.js';
```

Before the layer loop in `createLayers`, compute the metric range:

```javascript
    // Compute metric range for color mapping
    const allNodes = Object.values(layerGroups).flat();
    const metricRange = computeMetricRange(allNodes);
```

Replace the height line (line ~111):

```javascript
                const height = computeHeight(node);
```

Replace the color line (line ~120):

```javascript
                const color = computeColor(node, metricRange);
```

**Step 3: Verify the viewer still renders correctly**

Run `callgraph serve`, open browser. Blocks should look the same as before — "complexity" default uses lines_of_code for C4, child_count for higher levels (which matches the old LOC-only behavior for function-level blocks; container/component blocks may differ slightly since they now use child_count instead of aggregated LOC).

**Step 4: Commit**

```bash
git add web/js/graph-loader.js web/js/layers.js web/js/main.js
git commit -m "feat: wire metrics.js into graph loader and layer renderer"
```

---

### Task 3: Add metric dropdowns to config panel

**Files:**
- Modify: `web/index.html`
- Modify: `web/js/config-panel.js`

**Step 1: Add dropdown HTML to index.html**

In `web/index.html`, add CSS for the dropdown styling. Add after the `.config-item label` rule:

```css
        .config-item select {
            flex: 1;
            padding: 3px 6px;
            border: 1px solid #cccad2;
            border-radius: 3px;
            background: #fff;
            color: #353148;
            font-family: monospace;
            font-size: 11px;
            cursor: pointer;
            outline: none;
        }
        .config-item select:focus {
            border-color: #8c60f3;
        }
```

Add a new config section in `#config-content`, right after the opening `<div id="config-content">` — this should be the FIRST section (before Layers):

```html
            <div class="config-section">
                <div class="config-section-title">Metrics</div>
                <div class="config-item">
                    <label for="metric-size">Size</label>
                    <select id="metric-size">
                        <option value="complexity" selected>Complexity</option>
                        <option value="lines_of_code">Lines of Code</option>
                        <option value="export_count">Export Count</option>
                        <option value="fan_in">Fan In</option>
                        <option value="fan_out">Fan Out</option>
                        <option value="child_count">Child Count</option>
                    </select>
                </div>
                <div class="config-item">
                    <label for="metric-color">Color</label>
                    <select id="metric-color">
                        <option value="language" selected>Language</option>
                        <option value="lines_of_code">Lines of Code</option>
                        <option value="export_count">Export Count</option>
                        <option value="fan_in">Fan In</option>
                        <option value="fan_out">Fan Out</option>
                        <option value="child_count">Child Count</option>
                    </select>
                </div>
            </div>
            <div class="config-divider"></div>
```

**Step 2: Wire dropdowns in config-panel.js**

Add imports at top of `config-panel.js`:

```javascript
import * as THREE from 'three';
import { setSizeMetric, setColorMetric, computeHeight, computeColor, computeMetricRange } from './metrics.js';
```

Add at the end of `initConfigPanel`, before the closing `}`:

```javascript
    // Metric dropdowns
    function reapplyMetrics() {
        const metricRange = computeMetricRange(
            Array.from(nodeDataMap.values())
        );
        for (const [mesh, data] of nodeDataMap) {
            // Update height
            const newHeight = computeHeight(data);
            const oldHeight = mesh.geometry.parameters.height;
            if (Math.abs(newHeight - oldHeight) > 0.01) {
                const w = mesh.geometry.parameters.width;
                const d = mesh.geometry.parameters.depth;
                mesh.geometry.dispose();
                mesh.geometry = new THREE.BoxGeometry(w, newHeight, d);
                const level = data.abstraction_level ?? 0;
                const layerY = level * 12;
                mesh.position.y = layerY + newHeight / 2 + 0.1;
            }

            // Update color
            const newColor = computeColor(data, metricRange);
            mesh.material.color.setHex(newColor);
            mesh.material.emissive.setHex(newColor);
            mesh.material.emissiveIntensity = 0.15;
            mesh.userData._origColor = newColor;
        }
        requestRender('metrics');
    }

    const sizeSelect = document.getElementById('metric-size');
    if (sizeSelect) {
        sizeSelect.addEventListener('change', () => {
            setSizeMetric(sizeSelect.value);
            reapplyMetrics();
        });
    }

    const colorSelect = document.getElementById('metric-color');
    if (colorSelect) {
        colorSelect.addEventListener('change', () => {
            setColorMetric(colorSelect.value);
            reapplyMetrics();
        });
    }
```

**Step 3: Verify dropdowns work**

Run `callgraph serve`, open browser:
- Default "Complexity" — C4 blocks sized by LOC, C2/C3 by child count
- Change "Size" to "fan_out" — all blocks resize by outgoing edges
- Change "Color" to "lines_of_code" — blocks show blue-to-red gradient
- Change "Color" back to "Language" — blocks return to purple palette

**Step 4: Commit**

```bash
git add web/index.html web/js/config-panel.js
git commit -m "feat: add metric dropdowns to config panel with complexity default"
```

---

### Task 4: Update info panel to show active metric

**Files:**
- Modify: `web/index.html`
- Modify: `web/js/interaction.js`

**Step 1: Add dynamic label to info panel HTML**

In `web/index.html`, replace:

```html
        <div class="field"><span class="label">LOC: </span><span id="info-loc"></span></div>
```

With:

```html
        <div class="field"><span class="label" id="info-loc-label">LOC: </span><span id="info-loc"></span></div>
```

**Step 2: Show active metric in info panel**

In `web/js/interaction.js`, add import:

```javascript
import { getSizeInfo } from './metrics.js';
```

In the `showInfoPanel` function, replace:

```javascript
    document.getElementById('info-loc').textContent = data.lines_of_code;
```

With:

```javascript
    const { metric, value } = getSizeInfo(data);
    const sizeLabel = document.getElementById('info-loc-label');
    if (sizeLabel) sizeLabel.textContent = metric.replace(/_/g, ' ') + ': ';
    document.getElementById('info-loc').textContent = value;
```

**Step 3: Verify info panel updates**

Run `callgraph serve`, hover a block:
- With "Complexity" selected: C4 function shows "lines of code: 42", C2 container shows "child count: 5"
- Change size to "fan_out": all blocks show "fan out: N"

**Step 4: Commit**

```bash
git add web/js/interaction.js web/index.html
git commit -m "feat: info panel shows active metric value"
```

---

### Task 5: Verify full integration and push

**Step 1: Full smoke test**

Run `callgraph serve` and verify:
1. Default view: size=Complexity (LOC for functions, child_count for modules), color=Language
2. Size dropdown: each option resizes blocks correctly
3. "Complexity" uses LOC for C4, child_count for C3/C2/C1
4. Color dropdown: "language" = categorical, numeric = blue-to-red gradient
5. Info panel: label and value update per metric and per layer level
6. Hover highlighting still works (colors reset properly after hover)
7. Diff mode toggle still works (overrides colors when active)
8. Config panel checkboxes (layers, types, edges, languages) still work

**Step 2: Commit any fixes**

```bash
git add -A
git commit -m "fix: address issues from integration testing"
```

**Step 3: Push**

```bash
git push
```
