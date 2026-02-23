import * as THREE from 'three';

const ROLE_COLORS = {
    data: 0x00E5CC,
    control: 0xFF6B35,
    mixed: 0x9E9E9E,
};

const TUBE_RADIUS_MIN = 0.08;
const TUBE_RADIUS_MAX = 0.35;
const WEIGHT_MAX = 30;
const ARROWHEAD_LENGTH = 1.2;
const ARROWHEAD_RADIUS = 0.5;
const MIN_SEG_FOR_ARROW = 3;
const PORT_MARGIN = 0.3;           // margin from box edge for port grid
const STUB_LEN = 3;               // how far edges extend perpendicular from face before routing

/**
 * Create circuit-style orthogonal edges for C3/C2 semantic relationships.
 * Uses port-based attachment: each node face has a grid of ports so edges
 * never share the same exit/entry point.
 */
export function createSemanticEdges(semanticData, nodeMeshes, scene) {
    if (!semanticData || !semanticData.edges) return [];

    const edgeGroups = [];

    // Collect all connections per node to allocate ports per face
    const nodeConns = new Map(); // nodeId -> [{ edge, role: 'src'|'tgt', otherPos }]
    for (const edge of semanticData.edges) {
        const fromMesh = nodeMeshes[edge.from];
        const toMesh = nodeMeshes[edge.to];
        if (!fromMesh || !toMesh || fromMesh === toMesh) continue;

        if (!nodeConns.has(edge.from)) nodeConns.set(edge.from, []);
        nodeConns.get(edge.from).push({ edge, role: 'src', otherPos: toMesh.position });

        if (!nodeConns.has(edge.to)) nodeConns.set(edge.to, []);
        nodeConns.get(edge.to).push({ edge, role: 'tgt', otherPos: fromMesh.position });
    }

    // Assign each connection to a face and a port on that face
    const portAssignments = new Map(); // key -> { pos: Vector3, normal: Vector3 }
    for (const [nodeId, conns] of nodeConns) {
        const mesh = nodeMeshes[nodeId];
        const params = mesh.geometry.parameters;
        const hw = params.width / 2;
        const hh = params.height / 2;
        const hd = params.depth / 2;
        const pos = mesh.position;

        // Group connections by face
        const faces = { '+x': [], '-x': [], '+z': [], '-z': [], '+y': [], '-y': [] };

        for (const conn of conns) {
            const face = pickFace(pos, conn.otherPos, hw, hh, hd);
            faces[face].push(conn);
        }

        // Assign port positions on each face
        for (const [face, faceConns] of Object.entries(faces)) {
            if (faceConns.length === 0) continue;
            const ports = computePortGrid(pos, face, hw, hh, hd, faceConns.length);
            const normal = faceNormal(face);
            for (let i = 0; i < faceConns.length; i++) {
                const conn = faceConns[i];
                const key = `${nodeId}::${conn.edge.from}::${conn.edge.to}::${conn.role}`;
                portAssignments.set(key, { pos: ports[i], normal });
            }
        }
    }

    // Build edges using assigned ports
    for (const edge of semanticData.edges) {
        const fromMesh = nodeMeshes[edge.from];
        const toMesh = nodeMeshes[edge.to];
        if (!fromMesh || !toMesh || fromMesh === toMesh) continue;

        const srcKey = `${edge.from}::${edge.from}::${edge.to}::src`;
        const tgtKey = `${edge.to}::${edge.from}::${edge.to}::tgt`;
        const srcPort = portAssignments.get(srcKey);
        const tgtPort = portAssignments.get(tgtKey);
        if (!srcPort || !tgtPort) continue;

        const start = srcPort.pos;
        const end = tgtPort.pos;

        const group = new THREE.Group();
        group.userData = { type: 'semantic-edge', edgeData: edge };

        // Determine edge role
        const types = edge.types || {};
        const callWeight = types.calls || 0;
        const importWeight = types.imports || 0;
        const role = callWeight > importWeight ? 'control' : importWeight > callWeight ? 'data' : 'mixed';
        const color = ROLE_COLORS[role] || ROLE_COLORS.mixed;

        // Circuit route: exit stub → orthogonal connection → entry stub
        const waypoints = computeStubRoute(start, srcPort.normal, end, tgtPort.normal);

        // Tube thickness from weight
        const t = Math.min((edge.weight || 1) / WEIGHT_MAX, 1);
        const radius = TUBE_RADIUS_MIN + t * (TUBE_RADIUS_MAX - TUBE_RADIUS_MIN);

        // Create tube along straight-line waypoints
        const curve = new THREE.CurvePath();
        for (let i = 0; i < waypoints.length - 1; i++) {
            curve.add(new THREE.LineCurve3(waypoints[i], waypoints[i + 1]));
        }
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

        // One arrowhead at midpoint of each long segment + final pulled-back arrow
        const arrowGeo = new THREE.ConeGeometry(ARROWHEAD_RADIUS, ARROWHEAD_LENGTH, 8);
        const arrowMat = new THREE.MeshPhongMaterial({ color, emissive: color, emissiveIntensity: 0.15 });
        const up = new THREE.Vector3(0, 1, 0);

        for (let i = 0; i < waypoints.length - 1; i++) {
            const segStart = waypoints[i];
            const segEnd = waypoints[i + 1];
            const segVec = segEnd.clone().sub(segStart);
            const segLen = segVec.length();
            if (segLen < MIN_SEG_FOR_ARROW) continue;

            const dir = segVec.clone().normalize();
            const midPos = segStart.clone().add(segEnd).multiplyScalar(0.5);
            const arrow = new THREE.Mesh(arrowGeo, arrowMat);
            arrow.position.copy(midPos);
            arrow.quaternion.copy(new THREE.Quaternion().setFromUnitVectors(up, dir));
            group.add(arrow);
        }

        // Final arrowhead pulled back from target
        const lastDir = waypoints[waypoints.length - 1].clone().sub(waypoints[waypoints.length - 2]).normalize();
        const finalArrow = new THREE.Mesh(arrowGeo, arrowMat);
        finalArrow.position.copy(end).addScaledVector(lastDir, -ARROWHEAD_LENGTH * 1.5);
        finalArrow.quaternion.copy(new THREE.Quaternion().setFromUnitVectors(up, lastDir));
        group.add(finalArrow);

        // Label sprite
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
 * Pick the best face of a box for an edge connecting to otherPos.
 * Same-layer: side faces only (+x, -x, +z, -z).
 * Cross-layer: also allow top/bottom (+y, -y).
 * Within allowed faces, pick nearest.
 */
function pickFace(pos, otherPos, hw, hh, hd) {
    const dx = otherPos.x - pos.x;
    const dy = otherPos.y - pos.y;
    const dz = otherPos.z - pos.z;
    const sameLayer = Math.abs(dy) < 1;

    const candidates = [
        { face: '+x', dist: Math.abs(dx - hw),  axis: 'side' },
        { face: '-x', dist: Math.abs(dx + hw),  axis: 'side' },
        { face: '+z', dist: Math.abs(dz - hd),  axis: 'side' },
        { face: '-z', dist: Math.abs(dz + hd),  axis: 'side' },
        { face: '+y', dist: Math.abs(dy - hh),  axis: 'vert' },
        { face: '-y', dist: Math.abs(dy + hh),  axis: 'vert' },
    ];

    // For same-layer, only side faces. For cross-layer, prefer the dominant axis.
    const allowed = sameLayer
        ? candidates.filter(c => c.axis === 'side')
        : candidates;

    // Pick face closest to the direction of the other node
    // Use projected distance along each face normal
    const scored = allowed.map(c => {
        let alignment;
        switch (c.face) {
            case '+x': alignment = dx / (Math.abs(dx) + Math.abs(dy) + Math.abs(dz) + 0.001); break;
            case '-x': alignment = -dx / (Math.abs(dx) + Math.abs(dy) + Math.abs(dz) + 0.001); break;
            case '+z': alignment = dz / (Math.abs(dx) + Math.abs(dy) + Math.abs(dz) + 0.001); break;
            case '-z': alignment = -dz / (Math.abs(dx) + Math.abs(dy) + Math.abs(dz) + 0.001); break;
            case '+y': alignment = dy / (Math.abs(dx) + Math.abs(dy) + Math.abs(dz) + 0.001); break;
            case '-y': alignment = -dy / (Math.abs(dx) + Math.abs(dy) + Math.abs(dz) + 0.001); break;
        }
        return { ...c, alignment };
    });

    scored.sort((a, b) => b.alignment - a.alignment);
    return scored[0].face;
}

/**
 * Compute a grid of port positions on a given face of a box.
 * Returns array of Vector3 world positions.
 */
function computePortGrid(pos, face, hw, hh, hd, count) {
    const cols = Math.ceil(Math.sqrt(count));
    const rows = Math.ceil(count / cols);

    // Determine the face plane and its two tangent axes
    let faceCenter, uAxis, vAxis, uHalf, vHalf;
    switch (face) {
        case '+x':
            faceCenter = new THREE.Vector3(pos.x + hw, pos.y, pos.z);
            uAxis = new THREE.Vector3(0, 0, 1); vAxis = new THREE.Vector3(0, 1, 0);
            uHalf = hd; vHalf = hh;
            break;
        case '-x':
            faceCenter = new THREE.Vector3(pos.x - hw, pos.y, pos.z);
            uAxis = new THREE.Vector3(0, 0, 1); vAxis = new THREE.Vector3(0, 1, 0);
            uHalf = hd; vHalf = hh;
            break;
        case '+z':
            faceCenter = new THREE.Vector3(pos.x, pos.y, pos.z + hd);
            uAxis = new THREE.Vector3(1, 0, 0); vAxis = new THREE.Vector3(0, 1, 0);
            uHalf = hw; vHalf = hh;
            break;
        case '-z':
            faceCenter = new THREE.Vector3(pos.x, pos.y, pos.z - hd);
            uAxis = new THREE.Vector3(1, 0, 0); vAxis = new THREE.Vector3(0, 1, 0);
            uHalf = hw; vHalf = hh;
            break;
        case '+y':
            faceCenter = new THREE.Vector3(pos.x, pos.y + hh, pos.z);
            uAxis = new THREE.Vector3(1, 0, 0); vAxis = new THREE.Vector3(0, 0, 1);
            uHalf = hw; vHalf = hd;
            break;
        case '-y':
            faceCenter = new THREE.Vector3(pos.x, pos.y - hh, pos.z);
            uAxis = new THREE.Vector3(1, 0, 0); vAxis = new THREE.Vector3(0, 0, 1);
            uHalf = hw; vHalf = hd;
            break;
    }

    const usableU = Math.max(0.2, (uHalf - PORT_MARGIN) * 2);
    const usableV = Math.max(0.2, (vHalf - PORT_MARGIN) * 2);

    const ports = [];
    for (let i = 0; i < count; i++) {
        const col = i % cols;
        const row = Math.floor(i / cols);
        // Normalized position [-0.5, 0.5] within the usable area
        const u = cols === 1 ? 0 : (col / (cols - 1) - 0.5);
        const v = rows === 1 ? 0 : (row / (rows - 1) - 0.5);

        const portPos = faceCenter.clone()
            .addScaledVector(uAxis, u * usableU)
            .addScaledVector(vAxis, v * usableV);
        ports.push(portPos);
    }

    return ports;
}

/** Face name → outward unit normal */
function faceNormal(face) {
    switch (face) {
        case '+x': return new THREE.Vector3(1, 0, 0);
        case '-x': return new THREE.Vector3(-1, 0, 0);
        case '+z': return new THREE.Vector3(0, 0, 1);
        case '-z': return new THREE.Vector3(0, 0, -1);
        case '+y': return new THREE.Vector3(0, 1, 0);
        case '-y': return new THREE.Vector3(0, -1, 0);
    }
}

/**
 * Build an orthogonal (circuit-style) route between two ports.
 *
 * 1. Exit stub: go along srcNormal by STUB_LEN  (clears the source node)
 * 2. Entry stub: go along tgtNormal by STUB_LEN  (clears the target node)
 * 3. Connect stub endpoints with at most 3 orthogonal segments,
 *    preserving the unique coordinates from each stub so paths never merge.
 */
function computeStubRoute(start, srcNormal, end, tgtNormal) {
    const exitPt = start.clone().addScaledVector(srcNormal, STUB_LEN);
    const entryPt = end.clone().addScaledVector(tgtNormal, STUB_LEN);

    // Connect exitPt → entryPt with orthogonal segments.
    // Strategy: move along X first (to midX), then Z, then Y — using
    // the stub endpoints' unique coords so parallel edges stay separated.
    const dx = entryPt.x - exitPt.x;
    const dy = entryPt.y - exitPt.y;
    const dz = entryPt.z - exitPt.z;

    const midPoints = [];

    if (Math.abs(dy) < 0.5) {
        // Same layer: route on XZ plane — only axis-aligned segments
        const midX = (exitPt.x + entryPt.x) / 2;
        midPoints.push(
            new THREE.Vector3(midX, exitPt.y, exitPt.z),
            new THREE.Vector3(midX, exitPt.y, entryPt.z),
            new THREE.Vector3(midX, entryPt.y, entryPt.z),
        );
    } else {
        // Cross-layer: only axis-aligned segments through Y
        const midY = (exitPt.y + entryPt.y) / 2;
        midPoints.push(
            new THREE.Vector3(exitPt.x, midY, exitPt.z),
            new THREE.Vector3(exitPt.x, midY, entryPt.z),
            new THREE.Vector3(entryPt.x, midY, entryPt.z),
        );
    }

    // Remove duplicate consecutive points
    const raw = [start.clone(), exitPt, ...midPoints, entryPt, end.clone()];
    const waypoints = [raw[0]];
    for (let i = 1; i < raw.length; i++) {
        if (raw[i].distanceTo(raw[i - 1]) > 0.01) {
            waypoints.push(raw[i]);
        }
    }
    return waypoints;
}

function createLabelSprite(text, color) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = 512;
    canvas.height = 64;

    ctx.font = 'bold 24px monospace';
    const metrics = ctx.measureText(text);
    const textW = metrics.width;
    const pillW = textW + 20;
    const pillH = 36;
    const pillX = (canvas.width - pillW) / 2;
    const pillY = (canvas.height - pillH) / 2;

    ctx.fillStyle = 'rgba(248, 246, 252, 0.85)';
    ctx.beginPath();
    ctx.roundRect(pillX, pillY, pillW, pillH, 6);
    ctx.fill();
    ctx.strokeStyle = `#${new THREE.Color(color).getHexString()}`;
    ctx.lineWidth = 2;
    ctx.stroke();

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
