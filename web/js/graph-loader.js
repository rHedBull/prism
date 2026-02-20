export async function loadGraph(basePath = '..') {
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
        if (node.type !== 'file') continue;
        const level = node.abstraction_level ?? 1;
        if (!layers[level]) layers[level] = [];
        layers[level].push(node);
    }
    return layers;
}
