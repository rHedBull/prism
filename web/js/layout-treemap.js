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

    for (const { child: childLevel } of levels) {
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
            if (!parentRect) continue; // orphan nodes

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
