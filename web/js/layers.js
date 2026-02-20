import * as THREE from 'three';

const LAYER_COLORS = {
    0: 0x6688cc, // C4 Code — light blue
    1: 0x4466aa, // C3 Component — blue
    2: 0x44aa66, // C2 Container — green
    3: 0xaa44aa, // C1 Context — purple
};

const LANGUAGE_COLORS = {
    python: 0xE8A838,       // warm amber/gold
    typescript: 0x00BCD4,    // cyan/teal
    typescriptreact: 0x00BCD4,
    javascript: 0x8BC34A,    // yellow-green
    javascriptreact: 0x8BC34A,
};

const LAYER_LABELS = {
    0: 'C4 — Code',
    1: 'C3 — Component',
    2: 'C2 — Container',
    3: 'C1 — Context',
};

const LAYER_SPACING = 12;
const LOC_SCALE = 0.08;
export const LAYER_SIZE = 50;

export function createLayers(layerGroups, edges, scene) {
    const layerMeshes = {};
    const nodeMeshes = {};
    const nodeDataMap = new Map();

    // Track bounding boxes: nodeId -> { cx, cz, w, d } (center + dimensions)
    const nodeBounds = {};

    // Process layers top-down: C1 (3) -> C2 (2) -> C3 (1) -> C4 (0)
    const levels = [3, 2, 1, 0];

    for (const level of levels) {
        const y = level * LAYER_SPACING;
        const nodes = layerGroups[level] || [];
        if (nodes.length === 0) continue;

        // Add layer plane
        const planeGeo = new THREE.BoxGeometry(LAYER_SIZE, 0.15, LAYER_SIZE);
        const planeMat = new THREE.MeshPhongMaterial({
            color: LAYER_COLORS[level] || 0x666666,
            transparent: true,
            opacity: 0.15,
        });
        const plane = new THREE.Mesh(planeGeo, planeMat);
        plane.position.y = y;
        plane.userData = { type: 'layer', level };
        scene.add(plane);
        layerMeshes[level] = plane;

        // Wireframe border
        const borderGeo = new THREE.EdgesGeometry(new THREE.BoxGeometry(LAYER_SIZE, 0.15, LAYER_SIZE));
        const borderMat = new THREE.LineBasicMaterial({
            color: LAYER_COLORS[level] || 0x666666,
            transparent: true,
            opacity: 0.4,
        });
        const border = new THREE.LineSegments(borderGeo, borderMat);
        border.position.y = y;
        scene.add(border);

        // Layer label
        const label = createTextSprite(
            LAYER_LABELS[level] || `level ${level}`,
            LAYER_COLORS[level] || 0x666666,
            36
        );
        label.position.set(-LAYER_SIZE / 2 - 4, y + 1.5, 0);
        scene.add(label);

        // Group nodes by their _layerParent
        const byParent = {};
        for (const node of nodes) {
            const pid = node._layerParent || '_root';
            if (!byParent[pid]) byParent[pid] = [];
            byParent[pid].push(node);
        }

        // For each parent group, subdivide the parent's bounding box
        for (const [parentId, children] of Object.entries(byParent)) {
            let parentBox;
            if (parentId === '_root' || !nodeBounds[parentId]) {
                // Top level: use full layer
                const half = LAYER_SIZE / 2 - 2;
                parentBox = { cx: 0, cz: 0, w: half * 2, d: half * 2 };
            } else {
                parentBox = nodeBounds[parentId];
            }

            // Subdivide parent box into a grid for children
            const positions = subdivideBox(parentBox, children);

            for (const { node, box } of positions) {
                // Store this node's bounding box for the next layer down
                nodeBounds[node.id] = box;

                // Block height: log-scaled LOC
                const height = Math.max(0.8, Math.log2(Math.max(1, node.lines_of_code)) * LOC_SCALE * 8);

                // Block size: smaller fraction of allocated box, capped per level
                const maxSize = level === 3 ? 20 : level === 2 ? 10 : level === 1 ? 4 : 2;
                const fillRatio = level === 0 ? 0.6 : 0.5;
                const blockW = Math.min(maxSize, Math.max(0.5, box.w * fillRatio));
                const blockD = Math.min(maxSize, Math.max(0.5, box.d * fillRatio));

                const geo = new THREE.BoxGeometry(blockW, height, blockD);
                const color = LANGUAGE_COLORS[node.language] || 0x888888;
                const mat = new THREE.MeshPhongMaterial({
                    color,
                    emissive: color,
                    emissiveIntensity: 0.15,
                    shininess: 60,
                    transparent: true,
                    opacity: 1.0,
                });
                const mesh = new THREE.Mesh(geo, mat);
                mesh.position.set(box.cx, y + height / 2 + 0.1, box.cz);
                mesh.userData = { type: 'node', nodeData: node };
                scene.add(mesh);

                nodeMeshes[node.id] = mesh;
                nodeDataMap.set(mesh, node);
            }
        }
    }

    return { layerMeshes, nodeMeshes, nodeDataMap };
}

// Subdivide a bounding box into cells for N children, return { node, box } pairs
function subdivideBox(parentBox, children) {
    const n = children.length;
    if (n === 0) return [];

    const cols = Math.ceil(Math.sqrt(n));
    const rows = Math.ceil(n / cols);
    const padding = 0.3;

    const cellW = parentBox.w / cols;
    const cellD = parentBox.d / rows;
    const startX = parentBox.cx - parentBox.w / 2;
    const startZ = parentBox.cz - parentBox.d / 2;

    // Sort children by LOC descending so bigger blocks get placed first
    const sorted = [...children].sort((a, b) => (b.lines_of_code || 0) - (a.lines_of_code || 0));

    return sorted.map((node, i) => {
        const col = i % cols;
        const row = Math.floor(i / cols);
        const cx = startX + (col + 0.5) * cellW;
        const cz = startZ + (row + 0.5) * cellD;
        return {
            node,
            box: {
                cx,
                cz,
                w: cellW - padding,
                d: cellD - padding,
            },
        };
    });
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
