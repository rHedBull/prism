export async function loadGraph(basePath = '.') {
    const [nodesRes, edgesRes] = await Promise.all([
        fetch(`${basePath}/.callgraph/nodes.json`),
        fetch(`${basePath}/.callgraph/edges.json`),
    ]);
    const nodes = await nodesRes.json();
    const edges = await edgesRes.json();
    return { nodes, edges };
}

export function groupByAbstractionLevel(nodes) {
    const layers = {};
    for (const node of nodes) {
        // C4 (level 0): functions and classes; C3-C1 (levels 1-3): files
        if (node.type === 'function' || node.type === 'class') {
            const level = 0;
            if (!layers[level]) layers[level] = [];
            layers[level].push(node);
        } else if (node.type === 'file') {
            const level = node.abstraction_level ?? 2;
            if (!layers[level]) layers[level] = [];
            layers[level].push(node);
        }
    }
    return layers;
}
