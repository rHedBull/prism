/**
 * Right-side config panel: controls visibility of layers, node types, edge types, languages.
 */

export function initConfigPanel(graph, layerGroups, nodeMeshes, edgeMeshes, layerMeshes, nodeDataMap) {
    // Auto-populate languages from graph data
    const languages = new Set();
    for (const node of graph.nodes) {
        if (node.language) languages.add(node.language);
    }

    const section = document.getElementById('config-languages-section');
    for (const lang of [...languages].sort()) {
        const id = `lang-${lang}`;
        const item = document.createElement('div');
        item.className = 'config-item';

        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.id = id;
        cb.checked = true;

        const label = document.createElement('label');
        label.htmlFor = id;
        label.textContent = lang;

        item.appendChild(cb);
        item.appendChild(label);
        section.appendChild(item);
    }

    // Hide edges whose endpoints are hidden or whose type is unchecked
    function updateEdgeVisibility() {
        for (const line of edgeMeshes) {
            const { edgeData, fromMesh, toMesh } = line.userData;
            const typeCb = document.getElementById(`edge-${edgeData.type}`);
            const typeVisible = typeCb ? typeCb.checked : true;
            const endpointsVisible = fromMesh.visible && toMesh.visible;
            line.visible = typeVisible && endpointsVisible;
        }
    }

    // Layer toggles
    for (const level of [0, 1, 2, 3]) {
        const checkbox = document.getElementById(`layer-${level}`);
        if (!checkbox) continue;
        checkbox.addEventListener('change', () => {
            const visible = checkbox.checked;
            if (layerMeshes[level]) layerMeshes[level].visible = visible;
            for (const [mesh, data] of nodeDataMap) {
                const nodeLevel = data.abstraction_level ?? data._level;
                if (nodeLevel === level) mesh.visible = visible;
            }
            updateEdgeVisibility();
        });
    }

    // Node type toggles
    for (const type of ['function', 'class']) {
        const checkbox = document.getElementById(`type-${type}`);
        if (!checkbox) continue;
        checkbox.addEventListener('change', () => {
            const visible = checkbox.checked;
            for (const [mesh, data] of nodeDataMap) {
                if (data.type === type) mesh.visible = visible;
            }
            updateEdgeVisibility();
        });
    }

    // Edge type toggles
    for (const edgeType of ['imports', 'calls', 'inherits_from', 'depends_on']) {
        const checkbox = document.getElementById(`edge-${edgeType}`);
        if (!checkbox) continue;
        checkbox.addEventListener('change', () => {
            updateEdgeVisibility();
        });
    }

    // Language toggles
    for (const lang of languages) {
        const checkbox = document.getElementById(`lang-${lang}`);
        if (!checkbox) continue;
        checkbox.addEventListener('change', () => {
            const visible = checkbox.checked;
            for (const [mesh, data] of nodeDataMap) {
                if (data.language === lang) mesh.visible = visible;
            }
            updateEdgeVisibility();
        });
    }
}
