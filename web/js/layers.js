import * as THREE from 'three';

const LAYER_COLORS = {
    0: 0x4466aa, // models — blue
    1: 0x44aa66, // services — green
    2: 0xaa6644, // api/components — orange
    3: 0xaa44aa, // entry points — purple
};

const LANGUAGE_COLORS = {
    python: 0x3572A5,
    typescript: 0x3178C6,
    typescriptreact: 0x3178C6,
    javascript: 0xF7DF1E,
    javascriptreact: 0xF7DF1E,
};

const LAYER_LABELS = {
    0: 'models / types',
    1: 'services / hooks',
    2: 'api / components',
    3: 'entry points',
};

const LAYER_SPACING = 12;
const BLOCK_BASE = 1.5;
const LOC_SCALE = 0.06;
export const LAYER_SIZE = 40;

export function createLayers(layerGroups, edges, scene) {
    const layerMeshes = {};
    const nodeMeshes = {};
    const nodeDataMap = new Map();

    const levels = Object.keys(layerGroups).map(Number).sort();

    for (const level of levels) {
        const y = level * LAYER_SPACING;
        const nodes = layerGroups[level];

        // Layer plane
        const planeGeo = new THREE.BoxGeometry(LAYER_SIZE, 0.2, LAYER_SIZE);
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

        // Layer label
        const label = createTextSprite(LAYER_LABELS[level] || `level ${level}`, LAYER_COLORS[level] || 0x666666);
        label.position.set(-LAYER_SIZE / 2 - 3, y + 1, 0);
        scene.add(label);

        // Node blocks — simple grid layout for now, force-directed in Task 9
        const cols = Math.ceil(Math.sqrt(nodes.length));
        const spacing = LAYER_SIZE / (cols + 1);

        nodes.forEach((node, i) => {
            const col = i % cols;
            const row = Math.floor(i / cols);
            const x = (col - cols / 2) * spacing + spacing / 2;
            const z = (row - cols / 2) * spacing + spacing / 2;
            const height = Math.max(1, node.lines_of_code * LOC_SCALE);

            const geo = new THREE.BoxGeometry(BLOCK_BASE, height, BLOCK_BASE);
            const color = LANGUAGE_COLORS[node.language] || 0x888888;
            const mat = new THREE.MeshPhongMaterial({ color });
            const mesh = new THREE.Mesh(geo, mat);
            mesh.position.set(x, y + height / 2 + 0.1, z);
            mesh.userData = { type: 'node', nodeData: node };
            scene.add(mesh);

            nodeMeshes[node.id] = mesh;
            nodeDataMap.set(mesh, node);
        });
    }

    return { layerMeshes, nodeMeshes, nodeDataMap };
}

function createTextSprite(text, color = 0xffffff) {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');
    ctx.font = '28px monospace';
    ctx.fillStyle = `#${new THREE.Color(color).getHexString()}`;
    ctx.fillText(text, 10, 40);

    const texture = new THREE.CanvasTexture(canvas);
    const mat = new THREE.SpriteMaterial({ map: texture, transparent: true });
    const sprite = new THREE.Sprite(mat);
    sprite.scale.set(16, 2, 1);
    return sprite;
}
