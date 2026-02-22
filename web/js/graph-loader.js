import { computeDerivedMetrics } from './metrics.js';

export async function loadGraph(basePath = '.') {
    const [nodesRes, edgesRes] = await Promise.all([
        fetch(`${basePath}/.callgraph/nodes.json`),
        fetch(`${basePath}/.callgraph/edges.json`),
    ]);
    const nodes = await nodesRes.json();
    const edges = await edgesRes.json();
    return { nodes, edges };
}

export function groupByAbstractionLevel(nodes, edges = []) {
    const layers = {};
    const fileNodes = nodes.filter(n => n.type === 'file');
    const dirNodes = nodes.filter(n => n.type === 'directory');

    // C1 (level 3): system context — one block for the whole codebase
    const totalLoc = fileNodes.reduce((sum, f) => sum + (f.lines_of_code || 0), 0);
    const totalExports = fileNodes.reduce((sum, f) => sum + (f.export_count || 0), 0);
    const systemNode = {
        id: 'system:root',
        type: 'system',
        name: _inferProjectName(fileNodes),
        file_path: '.',
        language: null,
        lines_of_code: totalLoc,
        export_count: totalExports,
        abstraction_level: 3,
        _layerParent: null,
    };
    layers[3] = [systemNode];

    // C2 (level 2): containers — one block per top-level directory
    const topDirs = dirNodes.filter(d => !d.parent);
    layers[2] = [];
    for (const dir of topDirs) {
        const allFiles = fileNodes.filter(f => f.file_path.startsWith(dir.file_path + '/') || f.parent === dir.id);
        if (allFiles.length === 0) continue;
        const cLoc = allFiles.reduce((sum, f) => sum + (f.lines_of_code || 0), 0);
        const cExports = allFiles.reduce((sum, f) => sum + (f.export_count || 0), 0);
        const languages = [...new Set(allFiles.map(f => f.language).filter(Boolean))];
        layers[2].push({
            id: dir.id,
            type: 'container',
            name: dir.name,
            file_path: dir.file_path,
            language: languages[0],
            lines_of_code: cLoc,
            export_count: cExports,
            abstraction_level: 2,
            _layerParent: systemNode.id,
        });
    }

    // C3 (level 1): components — one block per leaf directory
    const leafDirs = _getLeafDirs(dirNodes);
    layers[1] = [];
    for (const dir of leafDirs) {
        const children = fileNodes.filter(f => f.parent === dir.id);
        if (children.length === 0) continue;
        const cLoc = children.reduce((sum, f) => sum + (f.lines_of_code || 0), 0);
        const cExports = children.reduce((sum, f) => sum + (f.export_count || 0), 0);
        const languages = [...new Set(children.map(f => f.language).filter(Boolean))];
        // Find which C2 container this component belongs to
        const topDir = dir.file_path.split('/')[0];
        const parentContainer = layers[2].find(c => c.file_path === topDir);
        layers[1].push({
            id: dir.id,
            type: 'component',
            name: dir.name,
            file_path: dir.file_path,
            language: languages[0],
            lines_of_code: cLoc,
            export_count: cExports,
            abstraction_level: 1,
            _layerParent: parentContainer ? parentContainer.id : systemNode.id,
            _childFileIds: new Set(children.map(f => f.id)),
        });
    }

    // C4 (level 0): individual functions and classes
    layers[0] = [];
    const componentLookup = new Map();
    for (const comp of layers[1]) {
        for (const fid of comp._childFileIds) {
            componentLookup.set(fid, comp.id);
        }
    }
    for (const node of nodes) {
        if (node.type === 'function' || node.type === 'class' || node.type === 'interface' || node.type === 'type_alias') {
            // parent is file:path, map file -> component
            const parentComponent = componentLookup.get(node.parent);
            layers[0].push({
                ...node,
                _layerParent: parentComponent || null,
            });
        }
    }

    // Compute derived metrics on all layer nodes
    const allNodes = Object.values(layers).flat();
    computeDerivedMetrics(allNodes, edges);

    return layers;
}

function _getLeafDirs(dirNodes) {
    const dirIds = new Set(dirNodes.map(d => d.id));
    const hasChildDir = new Set();
    for (const d of dirNodes) {
        if (d.parent && dirIds.has(d.parent)) {
            hasChildDir.add(d.parent);
        }
    }
    return dirNodes.filter(d => !hasChildDir.has(d.id));
}

function _inferProjectName(fileNodes) {
    if (fileNodes.length === 0) return 'system';
    const first = fileNodes[0].file_path;
    const root = first.split('/')[0];
    return root || 'system';
}
