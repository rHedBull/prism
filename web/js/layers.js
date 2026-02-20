import * as THREE from 'three';
import { computeForceLayout } from './layout.js';

const LAYER_COLORS = {
    0: 0x4466aa, // models — blue
    1: 0x44aa66, // services — green
    2: 0xaa6644, // api/components — orange
    3: 0xaa44aa, // entry points — purple
};

const LANGUAGE_COLORS = {
    python: 0xE8A838,       // warm amber/gold
    typescript: 0x00BCD4,    // cyan/teal
    typescriptreact: 0x00BCD4,
    javascript: 0x8BC34A,    // yellow-green
    javascriptreact: 0x8BC34A,
};

const LAYER_LABELS = {
    0: 'models / types',
    1: 'services / hooks',
    2: 'api / components',
    3: 'entry points',
};

const LAYER_SPACING = 12;
const LOC_SCALE = 0.08;
export const LAYER_SIZE = 40;

export function createLayers(layerGroups, edges, scene) {
    const layerMeshes = {};
    const nodeMeshes = {};
    const nodeDataMap = new Map();

    const levels = Object.keys(layerGroups).map(Number).sort();

    for (const level of levels) {
        const y = level * LAYER_SPACING;
        const nodes = layerGroups[level];

        // Layer plane — more visible
        const planeGeo = new THREE.BoxGeometry(LAYER_SIZE, 0.15, LAYER_SIZE);
        const planeMat = new THREE.MeshPhongMaterial({
            color: LAYER_COLORS[level] || 0x666666,
            transparent: true,
            opacity: 0.25,
        });
        const plane = new THREE.Mesh(planeGeo, planeMat);
        plane.position.y = y;
        plane.userData = { type: 'layer', level };
        scene.add(plane);
        layerMeshes[level] = plane;

        // Glowing wireframe border around layer
        const borderGeo = new THREE.EdgesGeometry(
            new THREE.BoxGeometry(LAYER_SIZE, 0.15, LAYER_SIZE)
        );
        const borderMat = new THREE.LineBasicMaterial({
            color: LAYER_COLORS[level] || 0x666666,
            transparent: true,
            opacity: 0.6,
        });
        const border = new THREE.LineSegments(borderGeo, borderMat);
        border.position.y = y;
        scene.add(border);

        // Layer label — larger, brighter
        const label = createTextSprite(
            LAYER_LABELS[level] || `level ${level}`,
            LAYER_COLORS[level] || 0x666666,
            36
        );
        label.position.set(-LAYER_SIZE / 2 - 4, y + 1.5, 0);
        scene.add(label);

        // Force-directed layout within this layer
        const positions = computeForceLayout(nodes, edges, 200, LAYER_SIZE / 2);

        nodes.forEach((node) => {
            const pos = positions[node.id];
            const x = pos.x;
            const z = pos.z;

            // Height: log-scaled LOC so large files don't tower absurdly
            const height = Math.max(0.8, Math.log2(Math.max(1, node.lines_of_code)) * LOC_SCALE * 8);

            // Base size: scale by export count — important files are wider
            const exportCount = node.export_count || 1;
            const baseSize = Math.min(3.0, 1.0 + exportCount * 0.25);

            const geo = new THREE.BoxGeometry(baseSize, height, baseSize);
            const color = LANGUAGE_COLORS[node.language] || 0x888888;
            const mat = new THREE.MeshPhongMaterial({
                color,
                emissive: color,
                emissiveIntensity: 0.15,
                shininess: 60,
            });
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
