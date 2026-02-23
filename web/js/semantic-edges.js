import * as THREE from 'three';

const ROLE_COLORS = {
    data: 0x00E5CC,
    control: 0xFF6B35,
    mixed: 0x9E9E9E,
};

const TUBE_RADIUS_MIN = 0.08;
const TUBE_RADIUS_MAX = 0.35;
const WEIGHT_MAX = 30;
const ARROWHEAD_LENGTH = 0.8;
const ARROWHEAD_RADIUS = 0.3;

/**
 * Create circuit-style orthogonal edges for C3/C2 semantic relationships.
 * Returns array of THREE.Group objects (each group = tube + arrowhead + label).
 */
export function createSemanticEdges(semanticData, nodeMeshes, scene) {
    if (!semanticData || !semanticData.edges) return [];

    const edgeGroups = [];

    for (const edge of semanticData.edges) {
        const fromMesh = nodeMeshes[edge.from];
        const toMesh = nodeMeshes[edge.to];
        if (!fromMesh || !toMesh) continue;
        if (fromMesh === toMesh) continue;

        const group = new THREE.Group();
        group.userData = { type: 'semantic-edge', edgeData: edge };

        const start = fromMesh.position.clone();
        const end = toMesh.position.clone();

        // Determine edge role from dominant edge types
        const types = edge.types || {};
        const callWeight = types.calls || 0;
        const importWeight = types.imports || 0;
        const role = callWeight > importWeight ? 'control' : importWeight > callWeight ? 'data' : 'mixed';
        const color = ROLE_COLORS[role] || ROLE_COLORS.mixed;

        // Build orthogonal waypoints (circuit routing)
        const waypoints = computeCircuitPath(start, end);

        // Tube thickness from weight
        const t = Math.min((edge.weight || 1) / WEIGHT_MAX, 1);
        const radius = TUBE_RADIUS_MIN + t * (TUBE_RADIUS_MAX - TUBE_RADIUS_MIN);

        // Create tube along waypoints
        const curve = new THREE.CatmullRomCurve3(waypoints, false, 'catmullrom', 0.01);
        const tubeGeo = new THREE.TubeGeometry(curve, 64, radius, 8, false);
        const tubeMat = new THREE.MeshPhongMaterial({
            color,
            transparent: true,
            opacity: 0.7,
            emissive: color,
            emissiveIntensity: 0.1,
        });
        const tube = new THREE.Mesh(tubeGeo, tubeMat);
        group.add(tube);

        // Arrowhead at the end
        const lastSeg = waypoints[waypoints.length - 1].clone().sub(waypoints[waypoints.length - 2]).normalize();
        const arrowGeo = new THREE.ConeGeometry(ARROWHEAD_RADIUS, ARROWHEAD_LENGTH, 8);
        const arrowMat = new THREE.MeshPhongMaterial({ color, emissive: color, emissiveIntensity: 0.15 });
        const arrow = new THREE.Mesh(arrowGeo, arrowMat);
        arrow.position.copy(end);
        // Orient cone along the last segment direction
        const up = new THREE.Vector3(0, 1, 0);
        const quat = new THREE.Quaternion().setFromUnitVectors(up, lastSeg);
        arrow.quaternion.copy(quat);
        group.add(arrow);

        // Label sprite at midpoint of the longest segment
        if (edge.label) {
            const midIdx = Math.floor(waypoints.length / 2);
            const labelPos = waypoints[midIdx].clone();
            labelPos.y += 1.2;
            const sprite = createLabelSprite(edge.label, color);
            sprite.position.copy(labelPos);
            group.add(sprite);
        }

        scene.add(group);
        edgeGroups.push(group);
    }

    return edgeGroups;
}

/**
 * Compute orthogonal (circuit-style) path between two 3D points.
 * Route: exit source horizontally on X → go vertical on Y → enter target horizontally on X.
 * If same Y level: L-shape on XZ plane with a midpoint jog.
 */
function computeCircuitPath(start, end) {
    const sameLayer = Math.abs(start.y - end.y) < 1;

    if (sameLayer) {
        // Same layer: L-shaped or Z-shaped route on the XZ plane
        const midX = (start.x + end.x) / 2;
        return [
            start.clone(),
            new THREE.Vector3(midX, start.y, start.z),
            new THREE.Vector3(midX, end.y, end.z),
            end.clone(),
        ];
    } else {
        // Cross-layer: exit horizontally, go vertical, enter horizontally
        const offsetX = (end.x - start.x) * 0.3;
        const midY = (start.y + end.y) / 2;
        return [
            start.clone(),
            new THREE.Vector3(start.x + offsetX, start.y, start.z),
            new THREE.Vector3(start.x + offsetX, midY, start.z),
            new THREE.Vector3(end.x - offsetX, midY, end.z),
            new THREE.Vector3(end.x - offsetX, end.y, end.z),
            end.clone(),
        ];
    }
}

function createLabelSprite(text, color) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = 512;
    canvas.height = 64;

    // Measure text to size the background pill
    ctx.font = 'bold 24px monospace';
    const metrics = ctx.measureText(text);
    const textW = metrics.width;
    const pillW = textW + 20;
    const pillH = 36;
    const pillX = (canvas.width - pillW) / 2;
    const pillY = (canvas.height - pillH) / 2;

    // Background pill
    ctx.fillStyle = 'rgba(248, 246, 252, 0.85)';
    ctx.beginPath();
    ctx.roundRect(pillX, pillY, pillW, pillH, 6);
    ctx.fill();
    ctx.strokeStyle = `#${new THREE.Color(color).getHexString()}`;
    ctx.lineWidth = 2;
    ctx.stroke();

    // Text
    ctx.fillStyle = `#${new THREE.Color(color).getHexString()}`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, canvas.width / 2, canvas.height / 2);

    const texture = new THREE.CanvasTexture(canvas);
    texture.premultiplyAlpha = true;
    const mat = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false });
    const sprite = new THREE.Sprite(mat);
    sprite.scale.set(10, 1.5, 1);
    return sprite;
}

/**
 * Show/hide semantic edges based on layer visibility.
 */
export function updateSemanticEdgeVisibility(edgeGroups, nodeMeshes) {
    for (const group of edgeGroups) {
        const edge = group.userData.edgeData;
        const fromMesh = nodeMeshes[edge.from];
        const toMesh = nodeMeshes[edge.to];
        group.visible = !!(fromMesh?.visible && toMesh?.visible);
    }
}
