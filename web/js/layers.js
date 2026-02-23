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

        // Compute grid size to fit all nodes with minimum cell spacing
        const n = nodes.length;
        const cellSize = MIN_CELL[level] || 4;
        const cols = Math.ceil(Math.sqrt(n));
        const rows = Math.ceil(n / cols);
        const gridW = Math.max(LAYER_SIZE, cols * cellSize);
        const gridD = Math.max(LAYER_SIZE, rows * cellSize);
        const actualCellW = gridW / cols;
        const actualCellD = gridD / rows;

        // Sort by parent group, then by LOC within each group, for spatial coherence
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

            // Block size: fraction of cell, capped per level
            const maxSize = level === 3 ? 20 : level === 2 ? 10 : level === 1 ? 4 : 2;
            const fillRatio = level === 0 ? 0.6 : 0.5;
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

        // Defer plane creation — compute from placed node positions
        deferredPlanes.push({ level, y, layerGroup, placedPositions });

        // Yield to browser after each layer so the page stays responsive
        if (onProgress) onProgress(level, nodes.length);
        await new Promise(r => setTimeout(r, 0));
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
    ctx.font = `bold ${fontSize}px monospace`;
    ctx.fillStyle = `#${new THREE.Color(color).getHexString()}`;
    ctx.fillText(text, 10, 44);

    const texture = new THREE.CanvasTexture(canvas);
    const mat = new THREE.SpriteMaterial({ map: texture, transparent: true });
    const sprite = new THREE.Sprite(mat);
    sprite.scale.set(18, 2.5, 1);
    return sprite;
}
