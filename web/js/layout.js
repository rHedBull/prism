// Force-directed layout for nodes within a layer, with boundary clamping
export function computeForceLayout(nodes, edges, iterations = 200, bounds = 17) {
    const nodeIds = new Set(nodes.map(n => n.id));
    const relevantEdges = edges.filter(e => nodeIds.has(e.from) && nodeIds.has(e.to));

    // Initialize positions randomly in a bounded area
    const positions = {};
    const AREA = bounds * 1.2;
    for (const node of nodes) {
        positions[node.id] = {
            x: (Math.random() - 0.5) * AREA,
            z: (Math.random() - 0.5) * AREA,
            vx: 0,
            vz: 0,
        };
    }

    const REPULSION = 50;
    const ATTRACTION = 0.03;
    const DAMPING = 0.9;
    const CENTER_PULL = 0.05;

    for (let iter = 0; iter < iterations; iter++) {
        // Repulsion between all pairs
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                const a = positions[nodes[i].id];
                const b = positions[nodes[j].id];
                let dx = a.x - b.x;
                let dz = a.z - b.z;
                let dist = Math.sqrt(dx * dx + dz * dz) + 0.01;
                let force = REPULSION / (dist * dist);
                let fx = (dx / dist) * force;
                let fz = (dz / dist) * force;
                a.vx += fx; a.vz += fz;
                b.vx -= fx; b.vz -= fz;
            }
        }

        // Attraction along edges
        for (const edge of relevantEdges) {
            const a = positions[edge.from];
            const b = positions[edge.to];
            if (!a || !b) continue;
            let dx = b.x - a.x;
            let dz = b.z - a.z;
            let dist = Math.sqrt(dx * dx + dz * dz) + 0.01;
            let force = dist * ATTRACTION;
            let fx = (dx / dist) * force;
            let fz = (dz / dist) * force;
            a.vx += fx; a.vz += fz;
            b.vx -= fx; b.vz -= fz;
        }

        // Center pull
        for (const node of nodes) {
            const p = positions[node.id];
            p.vx -= p.x * CENTER_PULL;
            p.vz -= p.z * CENTER_PULL;
        }

        // Apply velocity with damping
        for (const node of nodes) {
            const p = positions[node.id];
            p.vx *= DAMPING;
            p.vz *= DAMPING;
            p.x += p.vx;
            p.z += p.vz;

            // Clamp within bounds
            const margin = 2;
            const limit = bounds - margin;
            p.x = Math.max(-limit, Math.min(limit, p.x));
            p.z = Math.max(-limit, Math.min(limit, p.z));
        }
    }

    return positions;
}

// Clustered grid layout: group nodes by parent file, arrange clusters in a grid
export function computeClusteredLayout(nodes, bounds = 17) {
    // Group by parent file
    const clusters = {};
    for (const node of nodes) {
        const parent = node.parent || '_orphan';
        if (!clusters[parent]) clusters[parent] = [];
        clusters[parent].push(node);
    }

    const clusterKeys = Object.keys(clusters);
    const clusterCount = clusterKeys.length;

    // Arrange clusters in a grid
    const gridCols = Math.ceil(Math.sqrt(clusterCount));
    const gridRows = Math.ceil(clusterCount / gridCols);
    const cellSize = (bounds * 2) / Math.max(gridCols, gridRows);
    const padding = cellSize * 0.1;

    const positions = {};

    clusterKeys.forEach((key, idx) => {
        const col = idx % gridCols;
        const row = Math.floor(idx / gridCols);

        // Center of this cluster's cell
        const cx = (col - (gridCols - 1) / 2) * cellSize;
        const cz = (row - (gridRows - 1) / 2) * cellSize;

        const members = clusters[key];
        const innerCols = Math.ceil(Math.sqrt(members.length));
        const innerSpacing = (cellSize - padding * 2) / Math.max(innerCols, 1);

        members.forEach((node, i) => {
            const ic = i % innerCols;
            const ir = Math.floor(i / innerCols);
            positions[node.id] = {
                x: cx + (ic - (innerCols - 1) / 2) * innerSpacing,
                z: cz + (ir - (Math.ceil(members.length / innerCols) - 1) / 2) * innerSpacing,
            };
        });
    });

    return positions;
}
