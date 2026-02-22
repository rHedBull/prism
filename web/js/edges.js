import * as THREE from 'three';

const EDGE_COLORS = {
    imports: 0x8c60f3,
    calls: 0x353148,
    inherits_from: 0x6a3fd4,
    depends_on: 0x8e8a9c,
    contains: 0xcccad2,
};

export function createEdges(edges, nodeMeshes, scene, allNodes) {
    const edgeMeshes = [];

    // Build parent lookup: node ID -> parent ID
    // Build role lookup: node ID -> role
    const parentMap = {};
    const roleMap = {};
    if (allNodes) {
        for (const node of allNodes) {
            if (node.parent) {
                parentMap[node.id] = node.parent;
            }
            if (node.role) {
                roleMap[node.id] = node.role;
            }
        }
    }

    // Resolve a node ID to the nearest rendered mesh by walking up the parent chain
    function resolveMesh(nodeId) {
        let id = nodeId;
        const visited = new Set();
        while (id && !visited.has(id)) {
            if (nodeMeshes[id]) return nodeMeshes[id];
            visited.add(id);
            id = parentMap[id];
        }
        return null;
    }

    for (const edge of edges) {
        if (edge.type === 'contains') continue;

        const fromMesh = resolveMesh(edge.from);
        const toMesh = resolveMesh(edge.to);
        if (!fromMesh || !toMesh) continue;
        if (fromMesh === toMesh) continue;

        const start = fromMesh.position.clone();
        const end = toMesh.position.clone();

        // Control point
        const mid = start.clone().add(end).multiplyScalar(0.5);
        const isVertical = Math.abs(start.y - end.y) > 2;

        if (isVertical) {
            mid.x += (Math.random() - 0.5) * 3;
            mid.z += (Math.random() - 0.5) * 3;
        } else {
            mid.y += 2.5;
        }

        const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
        const points = curve.getPoints(20);
        const geometry = new THREE.BufferGeometry().setFromPoints(points);

        const color = EDGE_COLORS[edge.type] || 0x444444;
        const isCallEdge = edge.type === 'calls';
        const baseOpacity = isCallEdge ? 0.45 : 0.25;

        let line;
        if (isVertical && !isCallEdge) {
            const material = new THREE.LineDashedMaterial({
                color,
                transparent: true,
                opacity: baseOpacity,
                dashSize: 0.8,
                gapSize: 0.4,
            });
            line = new THREE.Line(geometry, material);
            line.computeLineDistances();
        } else {
            const material = new THREE.LineBasicMaterial({
                color,
                transparent: true,
                opacity: baseOpacity,
            });
            line = new THREE.Line(geometry, material);
        }

        // Classify edge role from endpoint roles
        const fromRole = roleMap[edge.from] || 'hybrid';
        const toRole = roleMap[edge.to] || 'hybrid';
        let edgeRole;
        if (fromRole === 'data' && toRole === 'data') edgeRole = 'data';
        else if (fromRole === 'control' && toRole === 'control') edgeRole = 'control';
        else edgeRole = 'mixed';

        line.userData = { type: 'edge', edgeData: edge, baseOpacity, fromMesh, toMesh, edgeRole };
        scene.add(line);
        edgeMeshes.push(line);
    }

    return edgeMeshes;
}

export function highlightEdges(edgeMeshes, nodeId, parentMap) {
    // Check if a node ID matches directly or via parent chain
    function matches(edgeNodeId, targetId) {
        let id = edgeNodeId;
        const visited = new Set();
        while (id && !visited.has(id)) {
            if (id === targetId) return true;
            visited.add(id);
            id = parentMap[id];
        }
        return false;
    }

    for (const line of edgeMeshes) {
        const edge = line.userData.edgeData;
        if (matches(edge.from, nodeId) || matches(edge.to, nodeId)) {
            line.material.opacity = 0.9;
        } else {
            line.material.opacity = 0.03;
        }
    }
}

export function resetEdgeHighlights(edgeMeshes) {
    for (const line of edgeMeshes) {
        line.material.opacity = line.userData.baseOpacity;
    }
}
