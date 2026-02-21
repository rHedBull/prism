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
