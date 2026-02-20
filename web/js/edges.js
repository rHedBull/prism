import * as THREE from 'three';

const EDGE_COLORS = {
    imports: 0x4488cc,
    calls: 0xE8A838,
    inherits_from: 0x8844cc,
    depends_on: 0x666666,
    contains: 0x333344,
};

export function createEdges(edges, nodeMeshes, scene, allNodes) {
    const edgeMeshes = [];

    // Build parent lookup: node ID -> parent ID (for resolving func -> file)
    const parentMap = {};
    if (allNodes) {
        for (const node of allNodes) {
            if (node.parent) {
                parentMap[node.id] = node.parent;
            }
        }
    }

    for (const edge of edges) {
        if (edge.type === 'contains') continue;

        // Resolve mesh: direct lookup, or fall back to parent file node
        const fromMesh = nodeMeshes[edge.from] || nodeMeshes[parentMap[edge.from]];
        const toMesh = nodeMeshes[edge.to] || nodeMeshes[parentMap[edge.to]];
        if (!fromMesh || !toMesh) continue;
        if (fromMesh === toMesh) continue; // skip same-file internal calls visually

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
        const baseOpacity = isCallEdge ? 0.25 : 0.12;

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

        line.userData = { type: 'edge', edgeData: edge, baseOpacity };
        scene.add(line);
        edgeMeshes.push(line);
    }

    return edgeMeshes;
}

export function highlightEdges(edgeMeshes, nodeId, parentMap) {
    for (const line of edgeMeshes) {
        const edge = line.userData.edgeData;
        // Match direct node ID or parent file ID for call edges
        const fromMatch = edge.from === nodeId || (parentMap && parentMap[edge.from] === nodeId);
        const toMatch = edge.to === nodeId || (parentMap && parentMap[edge.to] === nodeId);
        if (fromMatch || toMatch) {
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
