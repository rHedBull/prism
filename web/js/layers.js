import * as THREE from 'three';
import { computeForceLayout, computeClusteredLayout } from './layout.js';

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
export const LAYER_SIZE = 40;
const MIN_LAYER_SIZE = 40;

export function createLayers(layerGroups, edges, scene) {
    const layerMeshes = {};
    const nodeMeshes = {};
    const nodeDataMap = new Map();

    const levels = Object.keys(layerGroups).map(Number).sort();

    for (const level of levels) {
        const y = level * LAYER_SPACING;
        const nodes = layerGroups[level];

        // Scale layer size based on node count so dense layers spread out
        const layerSize = Math.max(MIN_LAYER_SIZE, Math.sqrt(nodes.length) * 6);

        // Layer plane — more visible
        const planeGeo = new THREE.BoxGeometry(layerSize, 0.15, layerSize);
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
            new THREE.BoxGeometry(layerSize, 0.15, layerSize)
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
        label.position.set(-layerSize / 2 - 4, y + 1.5, 0);
        scene.add(label);

        // Layout: clustered grid for C4 (Code), force-directed for others
        const positions = level === 0
            ? computeClusteredLayout(nodes, layerSize / 2)
            : computeForceLayout(nodes, edges, 200, layerSize / 2);

        nodes.forEach((node) => {
            const pos = positions[node.id];
            const x = pos.x;
            const z = pos.z;

            // Height: log-scaled LOC
            const height = Math.max(0.8, Math.log2(Math.max(1, node.lines_of_code)) * LOC_SCALE * 8);

            // Base size scales with abstraction level
            const exportCount = node.export_count || 1;
            let baseSize;
            if (level === 0) {
                baseSize = Math.min(2.0, 0.8 + exportCount * 0.15);
            } else if (level === 1) {
                baseSize = Math.min(5.0, 1.5 + exportCount * 0.2);
            } else if (level === 2) {
                baseSize = Math.min(8.0, 3.0 + Math.log2(exportCount + 1) * 1.5);
            } else {
                baseSize = Math.min(12.0, 5.0 + Math.log2(exportCount + 1) * 2);
            }

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
