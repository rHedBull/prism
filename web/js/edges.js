import * as THREE from 'three';

const EDGE_COLORS = {
    imports: 0x4488cc,
    calls: 0xcc8844,
    inherits_from: 0x8844cc,
    depends_on: 0x666666,
    contains: 0x333344,
};

export function createEdges(edges, nodeMeshes, scene) {
    const edgeMeshes = [];

    for (const edge of edges) {
        if (edge.type === 'contains') continue; // skip hierarchy edges

        const fromMesh = nodeMeshes[edge.from];
        const toMesh = nodeMeshes[edge.to];
        if (!fromMesh || !toMesh) continue;

        const start = fromMesh.position.clone();
        const end = toMesh.position.clone();

        // Control point: midpoint raised for cross-layer, offset for intra-layer
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

        let line;
        if (isVertical) {
            // Dashed lines for cross-layer edges
            const material = new THREE.LineDashedMaterial({
                color,
                transparent: true,
                opacity: 0.15,
                dashSize: 0.8,
                gapSize: 0.4,
            });
            line = new THREE.Line(geometry, material);
            line.computeLineDistances();
        } else {
            const material = new THREE.LineBasicMaterial({
                color,
                transparent: true,
                opacity: 0.15,
            });
            line = new THREE.Line(geometry, material);
        }

        line.userData = { type: 'edge', edgeData: edge };
        scene.add(line);
        edgeMeshes.push(line);
    }

    return edgeMeshes;
}

export function highlightEdges(edgeMeshes, nodeId) {
    for (const line of edgeMeshes) {
        const edge = line.userData.edgeData;
        if (edge.from === nodeId || edge.to === nodeId) {
            line.material.opacity = 0.9;
        } else {
            line.material.opacity = 0.03;
        }
    }
}

export function resetEdgeHighlights(edgeMeshes) {
    for (const line of edgeMeshes) {
        line.material.opacity = 0.15;
    }
}
