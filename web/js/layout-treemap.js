/**
 * Grid-packed card layout for 2D node-graph mode.
 * Computes { x, z, w, d } rectangles for every node across all layers,
 * with children nested inside their parent's rectangle.
 */
import { computeHeight } from './metrics.js';

const CARD_GAP = 1.5;
const ROW_GAP = 2.5;
const CONTAINER_PADDING = 3.0;
const LABEL_RESERVE = 3.5;

/**
 * Grid-pack items into rows within a target width.
 * Items: [{ id, w, d }] — each with its own width and depth.
 * Returns [{ id, x, z, w, d }] positioned relative to (0, 0).
 */
function gridPack(items, targetWidth, gap = CARD_GAP, rowGap = ROW_GAP) {
    if (items.length === 0) return [];

    // Sort alphabetically by name for spatial predictability
    const sorted = [...items].sort((a, b) => a.id.localeCompare(b.id));

    const placed = [];
    let curX = 0;
    let curZ = 0;
    let rowMaxD = 0;

    for (const item of sorted) {
        // Start new row if this item would exceed target width
        if (curX > 0 && curX + item.w > targetWidth) {
            curZ += rowMaxD + rowGap;
            curX = 0;
            rowMaxD = 0;
        }

        placed.push({ id: item.id, x: curX, z: curZ, w: item.w, d: item.d });
        curX += item.w + gap;
        rowMaxD = Math.max(rowMaxD, item.d);
    }

    return placed;
}

/**
 * Compute bounding box of placed items.
 */
function boundingBox(placed) {
    let maxX = 0, maxZ = 0;
    for (const p of placed) {
        maxX = Math.max(maxX, p.x + p.w);
        maxZ = Math.max(maxZ, p.z + p.d);
    }
    return { w: maxX, d: maxZ };
}

/**
 * Build a nested grid-packed layout for all layers.
 *
 * @param {Object} layerGroups — { 3: [C1 nodes], 2: [C2], 1: [C3], 0: [C4] }
 * @param {number} totalW — target width hint for the top-level layout
 * @param {number} totalD — (unused, kept for API compat)
 * @returns {Map<string, {x, z, w, d, level}>} — nodeId -> rectangle
 */
export function buildNestedTreemap(layerGroups, totalW, totalD) {
    const layout = new Map();

    // Index nodes by id for quick lookup
    const nodeById = {};
    for (const nodes of Object.values(layerGroups)) {
        for (const n of nodes) nodeById[n.id] = n;
    }

    // Group children by parent at each level
    function groupByParent(childLevel) {
        const groups = {};
        const childNodes = layerGroups[childLevel] || [];
        for (const node of childNodes) {
            const pid = node._layerParent || '_orphan';
            if (!groups[pid]) groups[pid] = [];
            groups[pid].push(node);
        }
        return groups;
    }

    // --- Bottom-up sizing: compute card sizes for each node ---
    // containerSize[id] = { w, d } — the natural size of this node's card/container
    const containerSize = {};

    // Level 0 (C4): leaf cards sized by name + metric height
    for (const node of (layerGroups[0] || [])) {
        const w = Math.min(14, Math.max(4, node.name.length * 0.6));
        const metricH = computeHeight(node);
        const d = Math.min(8, Math.max(2, metricH * 1.5));
        containerSize[node.id] = { w, d };
    }

    // Levels 1, 2, 3: containers that grid-pack their children
    for (const parentLevel of [1, 2, 3]) {
        const childLevel = parentLevel - 1;
        const groups = groupByParent(childLevel);
        const parentNodes = layerGroups[parentLevel] || [];

        for (const pNode of parentNodes) {
            const children = groups[pNode.id] || [];
            if (children.length === 0) {
                // Empty container — minimum card size
                const w = Math.min(14, Math.max(4, pNode.name.length * 0.6));
                containerSize[pNode.id] = { w, d: 4 };
                continue;
            }

            // Build child items with their computed sizes
            const childItems = children.map(c => {
                const sz = containerSize[c.id] || { w: 4, d: 3 };
                return { id: c.id, w: sz.w, d: sz.d };
            });

            // Target width for row packing: sqrt of total area * aspect
            const totalArea = childItems.reduce((s, c) => s + c.w * c.d, 0);
            const targetW = Math.max(20, Math.sqrt(totalArea) * 1.5);

            const placed = gridPack(childItems, targetW);
            const bb = boundingBox(placed);

            containerSize[pNode.id] = {
                w: bb.w + CONTAINER_PADDING * 2,
                d: bb.d + CONTAINER_PADDING * 2 + LABEL_RESERVE,
            };
        }
    }

    // --- Top-down positioning: place nodes in world coordinates ---

    // Place C1 nodes at the top level
    const c1Nodes = layerGroups[3] || [];
    if (c1Nodes.length === 0) return layout;

    const c1Items = c1Nodes.map(n => {
        const sz = containerSize[n.id] || { w: 10, d: 10 };
        return { id: n.id, w: sz.w, d: sz.d };
    });

    const c1Placed = gridPack(c1Items, totalW);
    for (const p of c1Placed) {
        layout.set(p.id, { x: p.x, z: p.z, w: p.w, d: p.d, level: 3 });
    }

    // Nest children inside parents for levels 2, 1, 0
    for (const parentLevel of [3, 2, 1]) {
        const childLevel = parentLevel - 1;
        const groups = groupByParent(childLevel);

        for (const [parentId, children] of Object.entries(groups)) {
            const parentRect = layout.get(parentId);
            if (!parentRect) continue;

            const innerX = parentRect.x + CONTAINER_PADDING;
            const innerZ = parentRect.z + CONTAINER_PADDING + LABEL_RESERVE;

            const childItems = children.map(c => {
                const sz = containerSize[c.id] || { w: 4, d: 3 };
                return { id: c.id, w: sz.w, d: sz.d };
            });

            const innerW = Math.max(1, parentRect.w - CONTAINER_PADDING * 2);
            const placed = gridPack(childItems, innerW);

            for (const p of placed) {
                layout.set(p.id, {
                    x: innerX + p.x,
                    z: innerZ + p.z,
                    w: p.w,
                    d: p.d,
                    level: childLevel,
                });
            }
        }
    }

    return layout;
}
