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

    // C1 (level 3): system context — from data or synthetic fallback
    const systemDirs = dirNodes.filter(d => d.abstraction_level === 3);
    layers[3] = [];
    if (systemDirs.length > 0) {
        // Systems defined in architecture.yaml
        for (const dir of systemDirs) {
            const allFiles = _getAllFilesUnder(dir, fileNodes);
            const cLoc = allFiles.reduce((sum, f) => sum + (f.lines_of_code || 0), 0);
            const cExports = allFiles.reduce((sum, f) => sum + (f.export_count || 0), 0);
            layers[3].push({
                id: dir.id,
                type: 'system',
                name: dir.name,
                file_path: dir.file_path,
                language: null,
                lines_of_code: cLoc,
                export_count: cExports,
                abstraction_level: 3,
                _layerParent: null,
            });
        }
    } else {
        // Fallback: one synthetic system for the whole codebase
        const totalLoc = fileNodes.reduce((sum, f) => sum + (f.lines_of_code || 0), 0);
        const totalExports = fileNodes.reduce((sum, f) => sum + (f.export_count || 0), 0);
        layers[3].push({
            id: 'system:root',
            type: 'system',
            name: _inferProjectName(nodes),
            file_path: '.',
            language: null,
            lines_of_code: totalLoc,
            export_count: totalExports,
            abstraction_level: 3,
            _layerParent: null,
        });
    }

    // C2 (level 2): containers — dirs with abstraction_level === 2
    const containerDirs = dirNodes.filter(d => d.abstraction_level === 2);
    // Fallback: if no containers detected, use top-level dirs (backward compat)
    const useDepthFallback = containerDirs.length === 0;
    const c2Dirs = useDepthFallback ? dirNodes.filter(d => !d.parent) : containerDirs;

    layers[2] = [];
    for (const dir of c2Dirs) {
        const allFiles = _getAllFilesUnder(dir, fileNodes);
        if (allFiles.length === 0) continue;
        const cLoc = allFiles.reduce((sum, f) => sum + (f.lines_of_code || 0), 0);
        const cExports = allFiles.reduce((sum, f) => sum + (f.export_count || 0), 0);
        const languages = [...new Set(allFiles.map(f => f.language).filter(Boolean))];
        // Find parent system if multiple systems exist
        const parentSystem = layers[3].length > 1
            ? _findSystemAncestor(dir, layers[3], dirNodes)
            : layers[3][0];
        layers[2].push({
            id: dir.id,
            type: 'container',
            name: dir.name,
            file_path: dir.file_path,
            language: languages[0],
            lines_of_code: cLoc,
            export_count: cExports,
            abstraction_level: 2,
            _layerParent: parentSystem ? parentSystem.id : null,
        });
    }

    // C3 (level 1): components — ALL dirs with abstraction_level === 1
    // Include non-leaf dirs too so the tree shows full nesting.
    const c1Dirs = useDepthFallback
        ? _getLeafDirs(dirNodes)
        : dirNodes.filter(d => d.abstraction_level === 1);
    layers[1] = [];
    // Build a set of level-1 dir IDs for parent lookup
    const c1DirIds = new Set(c1Dirs.map(d => d.id));
    for (const dir of c1Dirs) {
        const children = fileNodes.filter(f => f.parent === dir.id);
        if (children.length === 0) continue;
        const cLoc = children.reduce((sum, f) => sum + (f.lines_of_code || 0), 0);
        const cExports = children.reduce((sum, f) => sum + (f.export_count || 0), 0);
        const languages = [...new Set(children.map(f => f.language).filter(Boolean))];
        // First try to find a level-1 ancestor (nested component), then container
        const parentComponent = _findComponentAncestor(dir, c1DirIds, dirNodes);
        const parentContainer = parentComponent
            ? null
            : _findContainerAncestor(dir, layers[2], dirNodes);
        const layerParent = parentComponent
            || (parentContainer ? parentContainer.id : null)
            || (layers[3][0] ? layers[3][0].id : null);
        layers[1].push({
            id: dir.id,
            type: 'component',
            name: dir.name,
            file_path: dir.file_path,
            language: languages[0],
            lines_of_code: cLoc,
            export_count: cExports,
            abstraction_level: 1,
            _layerParent: layerParent,
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
    // Also map file -> container for root-level files not under any component
    const containerLookup = new Map();
    for (const c of layers[2]) {
        for (const f of fileNodes) {
            if (f.file_path.startsWith(c.file_path + '/') && !componentLookup.has(f.id)) {
                containerLookup.set(f.id, c.id);
            }
        }
    }
    const fallbackParent = layers[3][0] ? layers[3][0].id : null;
    for (const node of nodes) {
        if (node.type === 'function' || node.type === 'class' || node.type === 'interface' || node.type === 'type_alias') {
            // parent is file:path, map file -> component -> container -> system
            const parentComponent = componentLookup.get(node.parent)
                || containerLookup.get(node.parent)
                || fallbackParent;
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

function _inferProjectName(nodes) {
    if (nodes.length === 0) return 'system';
    // Count all nodes (files + functions) per top-level directory, skip test/build
    const skip = new Set(['tests', 'test', 'build', 'dist', 'docs', 'node_modules']);
    const topDirs = {};
    for (const n of nodes) {
        const parts = (n.file_path || '').split('/');
        if (parts.length > 1 && !skip.has(parts[0])) {
            topDirs[parts[0]] = (topDirs[parts[0]] || 0) + 1;
        }
    }
    const sorted = Object.entries(topDirs).sort((a, b) => b[1] - a[1]);
    return sorted.length > 0 ? sorted[0][0] : 'system';
}

function _getAllFilesUnder(dir, fileNodes) {
    return fileNodes.filter(f =>
        f.file_path.startsWith(dir.file_path + '/') || f.parent === dir.id
    );
}

function _getLeafAmong(dirs) {
    const dirPaths = new Set(dirs.map(d => d.file_path));
    return dirs.filter(d => {
        // A dir is a leaf if no other dir in the set is a child of it
        for (const other of dirPaths) {
            if (other !== d.file_path && other.startsWith(d.file_path + '/')) {
                return false;
            }
        }
        return true;
    });
}

function _findSystemAncestor(dir, systems, allDirs) {
    // Walk up parent chain to find nearest system (level 3)
    const dirById = new Map(allDirs.map(d => [d.id, d]));
    const systemIds = new Set(systems.map(s => s.id));
    let current = dir;
    while (current && current.parent) {
        if (systemIds.has(current.parent)) {
            return systems.find(s => s.id === current.parent);
        }
        current = dirById.get(current.parent);
    }
    // Fallback: match by path prefix
    const sorted = [...systems].sort((a, b) => b.file_path.length - a.file_path.length);
    return sorted.find(s => dir.file_path.startsWith(s.file_path + '/')) || systems[0] || null;
}

function _findComponentAncestor(dir, componentDirIds, allDirs) {
    // Walk up parent chain to find nearest level-1 component ancestor
    const dirById = new Map(allDirs.map(d => [d.id, d]));
    let current = dir;
    while (current && current.parent) {
        if (componentDirIds.has(current.parent)) {
            return current.parent;
        }
        current = dirById.get(current.parent);
    }
    return null;
}

function _findContainerAncestor(dir, containers, allDirs) {
    // Walk up parent chain to find nearest container (level 2)
    const dirById = new Map(allDirs.map(d => [d.id, d]));
    const containerIds = new Set(containers.map(c => c.id));
    let current = dir;
    while (current && current.parent) {
        if (containerIds.has(current.parent)) {
            return containers.find(c => c.id === current.parent);
        }
        current = dirById.get(current.parent);
    }
    // Fallback: match by path prefix
    const sorted = [...containers].sort((a, b) => b.file_path.length - a.file_path.length);
    return sorted.find(c => dir.file_path.startsWith(c.file_path + '/')) || null;
}
