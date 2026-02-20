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
    const fileNodes = nodes.filter(n => n.type === 'file');
    const dirNodes = nodes.filter(n => n.type === 'directory');

    // C4 (level 0): individual functions and classes
    for (const node of nodes) {
        if (node.type === 'function' || node.type === 'class') {
            if (!layers[0]) layers[0] = [];
            layers[0].push(node);
        }
    }

    // C3 (level 1): components — one block per leaf directory (aggregate files)
    const leafDirs = _getLeafDirs(dirNodes);
    for (const dir of leafDirs) {
        const children = fileNodes.filter(f => f.parent === dir.id);
        if (children.length === 0) continue;
        const totalLoc = children.reduce((sum, f) => sum + (f.lines_of_code || 0), 0);
        const totalExports = children.reduce((sum, f) => sum + (f.export_count || 0), 0);
        const languages = [...new Set(children.map(f => f.language).filter(Boolean))];
        if (!layers[1]) layers[1] = [];
        layers[1].push({
            id: dir.id,
            type: 'component',
            name: dir.name,
            file_path: dir.file_path,
            language: languages.length === 1 ? languages[0] : languages[0],
            lines_of_code: totalLoc,
            export_count: totalExports,
            abstraction_level: 1,
            _children: children,
        });
    }

    // C2 (level 2): containers — one block per top-level directory (backend, frontend)
    const topDirs = dirNodes.filter(d => !d.parent);
    for (const dir of topDirs) {
        const allFiles = fileNodes.filter(f => f.file_path.startsWith(dir.file_path + '/') || f.parent === dir.id);
        if (allFiles.length === 0) continue;
        const totalLoc = allFiles.reduce((sum, f) => sum + (f.lines_of_code || 0), 0);
        const totalExports = allFiles.reduce((sum, f) => sum + (f.export_count || 0), 0);
        const languages = [...new Set(allFiles.map(f => f.language).filter(Boolean))];
        if (!layers[2]) layers[2] = [];
        layers[2].push({
            id: dir.id,
            type: 'container',
            name: dir.name,
            file_path: dir.file_path,
            language: languages[0],
            lines_of_code: totalLoc,
            export_count: totalExports,
            abstraction_level: 2,
            _children: allFiles,
        });
    }

    // C1 (level 3): system context — one block for the whole codebase
    const totalLoc = fileNodes.reduce((sum, f) => sum + (f.lines_of_code || 0), 0);
    const totalExports = fileNodes.reduce((sum, f) => sum + (f.export_count || 0), 0);
    layers[3] = [{
        id: 'system:root',
        type: 'system',
        name: _inferProjectName(fileNodes),
        file_path: '.',
        language: null,
        lines_of_code: totalLoc,
        export_count: totalExports,
        abstraction_level: 3,
        _children: fileNodes,
    }];

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
