/**
 * Right-side config panel: controls visibility of layers, node types, edge types, languages.
 */
import * as THREE from 'three';
import { requestRender } from './scene.js';
import { setSizeMetric, setColorMetric, getColorMetric, computeHeight, computeColor, computeMetricRange } from './metrics.js';

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
            reapplyMetrics();
        });
    }

    // Node type toggles
    for (const type of ['function', 'class', 'interface', 'type_alias']) {
        const checkbox = document.getElementById(`type-${type}`);
        if (!checkbox) continue;
        checkbox.addEventListener('change', () => {
            const visible = checkbox.checked;
            for (const [mesh, data] of nodeDataMap) {
                if (data.type === type) mesh.visible = visible;
            }
            updateEdgeVisibility();
            reapplyMetrics();
        });
    }

    // Edge type toggles
    for (const edgeType of ['imports', 'calls', 'inherits_from', 'depends_on']) {
        const checkbox = document.getElementById(`edge-${edgeType}`);
        if (!checkbox) continue;
        checkbox.addEventListener('change', () => {
            updateEdgeVisibility();
            requestRender('config');
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
            reapplyMetrics();
        });
    }

    // Role toggles
    for (const role of ['data', 'control', 'hybrid']) {
        const checkbox = document.getElementById(`role-${role}`);
        if (!checkbox) continue;
        checkbox.addEventListener('change', () => {
            const visible = checkbox.checked;
            for (const [mesh, data] of nodeDataMap) {
                if (data.role === role) mesh.visible = visible;
            }
            updateEdgeVisibility();
            reapplyMetrics();
        });
    }

    // Metric dropdowns — recompute sizes and colors relative to visible blocks
    function reapplyMetrics() {
        const visibleNodes = [];
        for (const [mesh, data] of nodeDataMap) {
            if (mesh.visible) visibleNodes.push(data);
        }
        const metricRange = computeMetricRange(visibleNodes.length > 0 ? visibleNodes : Array.from(nodeDataMap.values()));

        for (const [mesh, data] of nodeDataMap) {
            if (!mesh.visible) continue;
            if (!mesh.geometry || !mesh.geometry.parameters) continue;

            // Update height
            const newHeight = computeHeight(data);
            const oldHeight = mesh.geometry.parameters.height;
            if (Math.abs(newHeight - oldHeight) > 0.01) {
                const w = mesh.geometry.parameters.width;
                const d = mesh.geometry.parameters.depth;
                mesh.geometry.dispose();
                mesh.geometry = new THREE.BoxGeometry(w, newHeight, d);
                const level = data.abstraction_level ?? 0;
                const layerY = level * 12;
                mesh.position.y = layerY + newHeight / 2 + 0.1;
            }

            // Update color
            const newColor = computeColor(data, metricRange);
            if (!mesh.material || !mesh.material.color) continue;
            mesh.material.color.setHex(newColor);
            if (mesh.material.emissive) mesh.material.emissive.setHex(newColor);
            mesh.material.emissiveIntensity = 0.15;
            mesh.userData._origColor = newColor;
        }

        // Recolor edges based on role when color metric is 'role'
        const EDGE_ROLE_COLORS = { data: 0x00E5CC, control: 0xFF6B35, mixed: 0x9E9E9E };
        const EDGE_TYPE_COLORS = { imports: 0x8c60f3, calls: 0x353148, inherits_from: 0x6a3fd4, depends_on: 0x8e8a9c };
        const isRoleMode = getColorMetric() === 'role';
        for (const line of edgeMeshes) {
            if (!line.material || !line.material.color) continue;
            if (isRoleMode) {
                const roleColor = EDGE_ROLE_COLORS[line.userData.edgeRole] || 0x9E9E9E;
                line.material.color.setHex(roleColor);
            } else {
                const typeColor = EDGE_TYPE_COLORS[line.userData.edgeData?.type] || 0x444444;
                line.material.color.setHex(typeColor);
            }
        }

        requestRender('metrics');
    }

    const sizeSelect = document.getElementById('metric-size');
    if (sizeSelect) {
        sizeSelect.addEventListener('change', () => {
            setSizeMetric(sizeSelect.value);
            reapplyMetrics();
        });
    }

    const colorSelect = document.getElementById('metric-color');
    if (colorSelect) {
        colorSelect.addEventListener('change', () => {
            setColorMetric(colorSelect.value);
            reapplyMetrics();
        });
    }
}
