import * as THREE from 'three';
import { computeHeight, computeColor, computeMetricRange } from './metrics.js';

const LAYER_COLORS = {
    0: 0x4A90D9, // C4 Code — blue
    1: 0x8c60f3, // C3 Component — vivid purple
    2: 0x2ECC71, // C2 Container — green
    3: 0xE74C3C, // C1 Context — red
};

const LAYER_LABELS = {
    0: 'C4 — Code',
    1: 'C3 — Component',
    2: 'C2 — Container',
    3: 'C1 — Context',
};

const LAYER_SPACING = 12;
export const LAYER_SIZE = 50;

// Minimum cell size per node at each level
const MIN_CELL = { 0: 4, 1: 6, 2: 12, 3: 22 };

// Padding between C3-projected group regions on the C4 layer
const GROUP_PADDING = 3;

/**
 * Squarified treemap: lay out group rectangles with near-square aspect ratios.
 * Each group gets area proportional to its node count.
 * Returns array of { id, x, z, w, d } for each group.
 */
function squarifiedLayout(groups, totalW, totalD) {
    const entries = Object.entries(groups)
        .map(([id, nodes]) => ({ id, count: nodes.length }))
        .sort((a, b) => b.count - a.count);

    const totalCount = entries.reduce((s, e) => s + e.count, 0);
    const totalArea = totalW * totalD;

    // Assign each entry its proportional area
    for (const e of entries) e.area = (e.count / totalCount) * totalArea;

    const rects = [];
    layoutRect(entries, 0, 0, totalW, totalD, rects);
    return rects;
}

function layoutRect(items, x, z, w, d, rects) {
    if (items.length === 0) return;
    if (items.length === 1) {
        rects.push({
            id: items[0].id,
            x: x + GROUP_PADDING / 2,
            z: z + GROUP_PADDING / 2,
            w: Math.max(2, w - GROUP_PADDING),
            d: Math.max(2, d - GROUP_PADDING),
        });
        return;
    }

    const totalArea = items.reduce((s, e) => s + e.area, 0);

    // Split along the longer side
    const horizontal = w >= d;
    const sideLen = horizontal ? d : w;

    // Squarified: greedily add items to a strip until aspect ratio worsens
    let bestRow = [items[0]];
    let bestWorst = Infinity;

    for (let i = 1; i <= items.length; i++) {
        const row = items.slice(0, i);
        const rowArea = row.reduce((s, e) => s + e.area, 0);
        const stripLen = rowArea / sideLen;

        // Compute worst aspect ratio in this row
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
            break; // Adding more items worsens aspect ratio
        }
    }

    // Lay out bestRow along the shorter side
    const rowArea = bestRow.reduce((s, e) => s + e.area, 0);
    const stripLen = rowArea / sideLen;
    let offset = 0;

    for (const item of bestRow) {
        const itemSide = item.area / stripLen;
        if (horizontal) {
            rects.push({
                id: item.id,
                x: x + GROUP_PADDING / 2,
                z: z + offset + GROUP_PADDING / 2,
                w: Math.max(2, stripLen - GROUP_PADDING),
                d: Math.max(2, itemSide - GROUP_PADDING),
            });
        } else {
            rects.push({
                id: item.id,
                x: x + offset + GROUP_PADDING / 2,
                z: z + GROUP_PADDING / 2,
                w: Math.max(2, itemSide - GROUP_PADDING),
                d: Math.max(2, stripLen - GROUP_PADDING),
            });
        }
        offset += itemSide;
    }

    // Recurse on remaining items in the leftover rectangle
    const rest = items.slice(bestRow.length);
    if (rest.length > 0) {
        if (horizontal) {
            layoutRect(rest, x + stripLen, z, w - stripLen, d, rects);
        } else {
            layoutRect(rest, x, z + stripLen, w, d - stripLen, rects);
        }
    }
}

export async function createLayers(layerGroups, edges, scene, onProgress) {
    const layerMeshes = {};
    const nodeMeshes = {};
    const nodeDataMap = new Map();

    // Compute metric range for color mapping
    const allNodes = Object.values(layerGroups).flat();
    const metricRange = computeMetricRange(allNodes);

    // Process layers top-down: C1 (3) -> C2 (2) -> C3 (1) -> C4 (0)
    const levels = [3, 2, 1, 0];

    // Deferred plane data — we create planes after placing nodes so we can size them
    const deferredPlanes = [];

    for (const level of levels) {
        const y = level * LAYER_SPACING;
        const nodes = layerGroups[level] || [];
        if (nodes.length === 0) continue;

        const layerGroup = new THREE.Group();
        layerGroup.userData = { type: 'layer', level };
        scene.add(layerGroup);
        layerMeshes[level] = layerGroup;

        // Track node positions placed on this layer for bounding box
        const placedPositions = [];

        if (level === 0) {
            // === C4 GROUP-AWARE LAYOUT ===
            // Phase 1: Group C4 nodes by their C3 parent
            const groups = {};
            for (const node of nodes) {
                const pid = node._layerParent || '_root';
                if (!groups[pid]) groups[pid] = [];
                groups[pid].push(node);
            }

            // Sort nodes within each group by LOC descending
            for (const g of Object.values(groups)) {
                g.sort((a, b) => (b.lines_of_code || 0) - (a.lines_of_code || 0));
            }

            // Compute total grid dimensions needed
            const n = nodes.length;
            const cellSize = MIN_CELL[0];
            const totalCols = Math.ceil(Math.sqrt(n));
            const totalRows = Math.ceil(n / totalCols);
            const gridW = Math.max(LAYER_SIZE, totalCols * cellSize);
            const gridD = Math.max(LAYER_SIZE, totalRows * cellSize);

            // Phase 2: Pack groups into rectangular regions
            const groupRects = squarifiedLayout(groups, gridW, gridD);

            // Phase 3: Place C4 nodes within each group's rectangle
            for (const rect of groupRects) {
                const groupNodes = groups[rect.id];
                const gn = groupNodes.length;
                const gCols = Math.max(1, Math.ceil(Math.sqrt(gn * (rect.w / rect.d))));
                const gRows = Math.max(1, Math.ceil(gn / gCols));
                const gCellW = rect.w / gCols;
                const gCellD = rect.d / gRows;

                for (let i = 0; i < groupNodes.length; i++) {
                    const node = groupNodes[i];
                    const col = i % gCols;
                    const row = Math.floor(i / gCols);
                    const cx = -gridW / 2 + rect.x + (col + 0.5) * gCellW;
                    const cz = -gridD / 2 + rect.z + (row + 0.5) * gCellD;

                    const height = computeHeight(node);
                    const maxSize = 2;
                    const fillRatio = 0.6;
                    const blockW = Math.min(maxSize, Math.max(0.5, (gCellW - 0.5) * fillRatio));
                    const blockD = Math.min(maxSize, Math.max(0.5, (gCellD - 0.5) * fillRatio));

                    const geo = new THREE.BoxGeometry(blockW, height, blockD);
                    const color = computeColor(node, metricRange);
                    const mat = new THREE.MeshPhongMaterial({
                        color,
                        emissive: color,
                        emissiveIntensity: 0.15,
                        shininess: 60,
                    });
                    const mesh = new THREE.Mesh(geo, mat);
                    mesh.position.set(cx, y + height / 2 + 0.1, cz);
                    mesh.userData = { type: 'node', nodeData: node, _origColor: color };
                    scene.add(mesh);

                    nodeMeshes[node.id] = mesh;
                    nodeDataMap.set(mesh, node);

                    placedPositions.push({ x: cx, z: cz, hw: blockW / 2, hd: blockD / 2 });
                }
            }
        } else {
            // === FLAT GRID LAYOUT for C1/C2/C3 ===
            const n = nodes.length;
            const cellSize = MIN_CELL[level] || 4;
            const cols = Math.ceil(Math.sqrt(n));
            const rows = Math.ceil(n / cols);
            const gridW = Math.max(LAYER_SIZE, cols * cellSize);
            const gridD = Math.max(LAYER_SIZE, rows * cellSize);
            const actualCellW = gridW / cols;
            const actualCellD = gridD / rows;

            const sorted = [...nodes].sort((a, b) => {
                const pa = a._layerParent || '';
                const pb = b._layerParent || '';
                if (pa !== pb) return pa.localeCompare(pb);
                return (b.lines_of_code || 0) - (a.lines_of_code || 0);
            });

            for (let i = 0; i < sorted.length; i++) {
                const node = sorted[i];
                const col = i % cols;
                const row = Math.floor(i / cols);
                const cx = -gridW / 2 + (col + 0.5) * actualCellW;
                const cz = -gridD / 2 + (row + 0.5) * actualCellD;

                const height = computeHeight(node);
                const maxSize = level === 3 ? 20 : level === 2 ? 10 : 4;
                const fillRatio = 0.5;
                const blockW = Math.min(maxSize, Math.max(0.5, (actualCellW - 0.5) * fillRatio));
                const blockD = Math.min(maxSize, Math.max(0.5, (actualCellD - 0.5) * fillRatio));

                const geo = new THREE.BoxGeometry(blockW, height, blockD);
                const color = computeColor(node, metricRange);
                const mat = new THREE.MeshPhongMaterial({
                    color,
                    emissive: color,
                    emissiveIntensity: 0.15,
                    shininess: 60,
                });
                const mesh = new THREE.Mesh(geo, mat);
                mesh.position.set(cx, y + height / 2 + 0.1, cz);
                mesh.userData = { type: 'node', nodeData: node, _origColor: color };
                scene.add(mesh);

                nodeMeshes[node.id] = mesh;
                nodeDataMap.set(mesh, node);

                placedPositions.push({ x: cx, z: cz, hw: blockW / 2, hd: blockD / 2 });
            }
        }

        // Defer plane creation — compute from placed node positions
        deferredPlanes.push({ level, y, layerGroup, placedPositions });

        // Yield to browser after each layer so the page stays responsive
        if (onProgress) onProgress(level, nodes.length);
        await new Promise(r => setTimeout(r, 0));
    }

    // Post-pass: reposition C3 nodes above the centroid of their C4 children
    // so parent components sit directly above their code blocks
    const c4Y = 0 * LAYER_SPACING;  // C4 level y
    const c3Y = 1 * LAYER_SPACING;  // C3 level y
    const c4Centroids = {};  // parentId → { sumX, sumZ, count }
    for (const [id, mesh] of Object.entries(nodeMeshes)) {
        if (Math.abs(mesh.position.y - c4Y) > 5) continue;  // only C4 nodes
        const nd = mesh.userData?.nodeData;
        const pid = nd?._layerParent;
        if (!pid) continue;
        if (!c4Centroids[pid]) c4Centroids[pid] = { sumX: 0, sumZ: 0, count: 0 };
        c4Centroids[pid].sumX += mesh.position.x;
        c4Centroids[pid].sumZ += mesh.position.z;
        c4Centroids[pid].count++;
    }

    // Reposition C3 meshes only — keep original placedPositions so the plane stays centered
    for (const [id, mesh] of Object.entries(nodeMeshes)) {
        if (Math.abs(mesh.position.y - c3Y) > 5) continue;
        const nd = mesh.userData?.nodeData;
        if (!nd) continue;
        const centroid = c4Centroids[nd.id];
        if (!centroid || centroid.count === 0) continue;
        mesh.position.x = centroid.sumX / centroid.count;
        mesh.position.z = centroid.sumZ / centroid.count;
    }

    // Now create planes sized to fit their nodes
    const PLANE_PADDING = 4;
    for (const { level, y, layerGroup, placedPositions } of deferredPlanes) {
        let planeW, planeD, cx, cz;
        if (placedPositions.length === 0) {
            planeW = LAYER_SIZE;
            planeD = LAYER_SIZE;
            cx = 0;
            cz = 0;
        } else {
            let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
            for (const p of placedPositions) {
                minX = Math.min(minX, p.x - p.hw);
                maxX = Math.max(maxX, p.x + p.hw);
                minZ = Math.min(minZ, p.z - p.hd);
                maxZ = Math.max(maxZ, p.z + p.hd);
            }
            planeW = Math.max(LAYER_SIZE, (maxX - minX) + PLANE_PADDING * 2);
            planeD = Math.max(LAYER_SIZE, (maxZ - minZ) + PLANE_PADDING * 2);
            cx = (minX + maxX) / 2;
            cz = (minZ + maxZ) / 2;
        }

        const planeGeo = new THREE.BoxGeometry(planeW, 0.15, planeD);
        const planeMat = new THREE.MeshPhongMaterial({
            color: LAYER_COLORS[level] || 0x666666,
            transparent: true,
            opacity: 0.15,
            depthWrite: false,
        });
        const plane = new THREE.Mesh(planeGeo, planeMat);
        plane.position.set(cx, y, cz);
        plane.userData = { type: 'layer', level };
        layerGroup.add(plane);

        // Wireframe border
        const borderGeo = new THREE.EdgesGeometry(new THREE.BoxGeometry(planeW, 0.15, planeD));
        const borderMat = new THREE.LineBasicMaterial({
            color: LAYER_COLORS[level] || 0x666666,
            transparent: true,
            opacity: 0.4,
        });
        const border = new THREE.LineSegments(borderGeo, borderMat);
        border.position.set(cx, y, cz);
        layerGroup.add(border);

        // Layer label
        const label = createTextSprite(
            LAYER_LABELS[level] || `level ${level}`,
            LAYER_COLORS[level] || 0x666666,
            36
        );
        label.position.set(cx - planeW / 2 - 4, y + 1.5, cz);
        layerGroup.add(label);
    }

    return { layerMeshes, nodeMeshes, nodeDataMap };
}

function createTextSprite(text, color = 0xffffff, fontSize = 28) {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.font = `bold ${fontSize}px monospace`;
    ctx.fillStyle = `#${new THREE.Color(color).getHexString()}`;
    ctx.fillText(text, 10, 44);

    const texture = new THREE.CanvasTexture(canvas);
    texture.premultiplyAlpha = true;
    const mat = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false });
    const sprite = new THREE.Sprite(mat);
    sprite.scale.set(18, 2.5, 1);
    return sprite;
}
