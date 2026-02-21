/**
 * Side panel with hierarchical tree view, search/filter, and graph sync.
 */
import * as THREE from 'three';
import { getDiffState } from './diff-overlay.js';

const TYPE_ICONS = {
    system: '\u25C6',
    container: '\u25E7',
    component: '\u25EB',
    file: '\u25FB',
    function: '\u0192',
    class: '\u25C8',
    directory: '\u25A4',
};

export function createTreePanel(graph, layerGroups, nodeMeshes, camera, controls, animateCameraFn) {
    const searchInput = document.getElementById('tree-search');
    const treeContainer = document.getElementById('tree-content');

    // Build a lookup: id -> node data (from the rendered layer groups)
    const nodeById = new Map();
    for (const level of [3, 2, 1, 0]) {
        for (const node of (layerGroups[level] || [])) {
            nodeById.set(node.id, { ...node, _level: level });
        }
    }

    // Build parent->children map from _layerParent
    const childrenOf = new Map();
    for (const [id, node] of nodeById) {
        const pid = node._layerParent;
        if (pid) {
            if (!childrenOf.has(pid)) childrenOf.set(pid, []);
            childrenOf.get(pid).push(id);
        }
    }

    // Find root nodes (no _layerParent or parent not in our set)
    const roots = [];
    for (const [id, node] of nodeById) {
        if (!node._layerParent || !nodeById.has(node._layerParent)) {
            roots.push(id);
        }
    }

    function sortIds(ids) {
        return ids.slice().sort((a, b) => {
            const na = nodeById.get(a)?.name || '';
            const nb = nodeById.get(b)?.name || '';
            return na.localeCompare(nb);
        });
    }

    // Track expanded state — roots start expanded
    const expanded = new Set();
    for (const id of roots) expanded.add(id);

    let selectedNodeId = null;
    const _rowById = new Map();

    function renderTree(filter = '') {
        // Clear all children safely
        _rowById.clear();
        while (treeContainer.firstChild) {
            treeContainer.removeChild(treeContainer.firstChild);
        }

        const lowerFilter = filter.toLowerCase();

        // If filtering, find all matching nodes and their ancestors
        let visibleNodes = null;
        if (lowerFilter) {
            visibleNodes = new Set();
            for (const [id, node] of nodeById) {
                if (matchesFilter(node, lowerFilter)) {
                    visibleNodes.add(id);
                    let pid = node._layerParent;
                    while (pid && nodeById.has(pid)) {
                        visibleNodes.add(pid);
                        pid = nodeById.get(pid)._layerParent;
                    }
                }
            }
        }

        for (const rootId of sortIds(roots)) {
            renderNode(rootId, 0, treeContainer, lowerFilter, visibleNodes);
        }
    }

    function matchesFilter(node, lowerFilter) {
        return (
            node.name.toLowerCase().includes(lowerFilter) ||
            (node.file_path && node.file_path.toLowerCase().includes(lowerFilter)) ||
            (node.type && node.type.toLowerCase().includes(lowerFilter)) ||
            (node.language && node.language.toLowerCase().includes(lowerFilter))
        );
    }

    function renderNode(nodeId, depth, container, lowerFilter, visibleNodes) {
        const node = nodeById.get(nodeId);
        if (!node) return;

        if (visibleNodes && !visibleNodes.has(nodeId)) return;

        const children = childrenOf.get(nodeId) || [];
        const hasChildren = children.length > 0;
        const isExpanded = expanded.has(nodeId) || (lowerFilter && visibleNodes);

        const row = document.createElement('div');
        row.className = 'tree-row';
        if (nodeId === selectedNodeId) row.classList.add('selected');
        row.style.paddingLeft = `${12 + depth * 16}px`;

        // Expand/collapse toggle
        const toggle = document.createElement('span');
        toggle.className = 'tree-toggle';
        if (hasChildren) {
            toggle.textContent = isExpanded ? '\u25BE' : '\u25B8';
            toggle.addEventListener('click', (e) => {
                e.stopPropagation();
                if (expanded.has(nodeId)) expanded.delete(nodeId);
                else expanded.add(nodeId);
                renderTree(searchInput.value);
            });
        } else {
            toggle.textContent = ' ';
        }
        row.appendChild(toggle);

        // Type icon
        const icon = document.createElement('span');
        icon.className = 'tree-icon';
        icon.textContent = TYPE_ICONS[node.type] || '\u2022';
        row.appendChild(icon);

        // Name
        const nameEl = document.createElement('span');
        nameEl.className = 'tree-name';
        nameEl.textContent = node.name;
        row.appendChild(nameEl);

        // Type badge
        const badge = document.createElement('span');
        badge.className = 'tree-badge';
        badge.textContent = node.type;
        row.appendChild(badge);

        // Diff indicator
        const { diffActive, addedIds, removedIds, modifiedIds, movedIds } = getDiffState();
        if (diffActive) {
            let diffColor = null;
            let diffLabel = null;
            if (addedIds.has(nodeId)) { diffColor = '#00E676'; diffLabel = '+'; }
            else if (removedIds.has(nodeId)) { diffColor = '#FF1744'; diffLabel = '\u2212'; }
            else if (modifiedIds.has(nodeId)) { diffColor = '#FFD600'; diffLabel = '~'; }
            else if (movedIds.has(nodeId)) { diffColor = '#448AFF'; diffLabel = '\u2192'; }

            if (diffColor) {
                // Color the row background
                row.style.background = `${diffColor}22`;
                row.style.borderLeft = `3px solid ${diffColor}`;
                // Color the name
                nameEl.style.color = diffColor;
                nameEl.style.fontWeight = 'bold';
                // Add diff badge
                const diffBadge = document.createElement('span');
                diffBadge.className = 'tree-badge';
                diffBadge.style.background = diffColor;
                diffBadge.style.color = '#000';
                diffBadge.style.fontWeight = 'bold';
                diffBadge.textContent = diffLabel;
                row.appendChild(diffBadge);
            } else {
                // Dim unchanged rows
                row.style.opacity = '0.4';
            }
        }

        // Hover: highlight in graph
        row.addEventListener('mouseenter', () => {
            if (window._treePanelHoverCallback) {
                window._treePanelHoverCallback(nodeId);
            }
        });

        row.addEventListener('mouseleave', () => {
            if (window._treePanelLeaveCallback) {
                window._treePanelLeaveCallback();
            }
        });

        // Double-click: focus camera on node
        row.addEventListener('dblclick', (e) => {
            e.stopPropagation();
            selectedNodeId = nodeId;
            focusOnNode(nodeId);
            renderTree(searchInput.value);
        });

        // Single click: select + toggle expand
        row.addEventListener('click', () => {
            selectedNodeId = nodeId;
            if (hasChildren) {
                if (expanded.has(nodeId)) expanded.delete(nodeId);
                else expanded.add(nodeId);
            }
            renderTree(searchInput.value);
        });

        container.appendChild(row);
        _rowById.set(nodeId, row);

        if (hasChildren && isExpanded) {
            for (const childId of sortIds(children)) {
                renderNode(childId, depth + 1, container, lowerFilter, visibleNodes);
            }
        }
    }

    function focusOnNode(nodeId) {
        const mesh = nodeMeshes[nodeId];
        if (!mesh) return;

        const pos = mesh.position.clone();
        const node = nodeById.get(nodeId);
        const level = node?._level ?? 0;

        const dist = level >= 2 ? 25 : level === 1 ? 15 : 10;
        const targetPos = pos.clone().add(
            new THREE.Vector3(dist * 0.7, dist * 0.5, dist * 0.7)
        );
        animateCameraFn(camera, controls, targetPos, pos.clone(), 800);
    }

    // Debounced search
    let searchTimeout;
    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            renderTree(searchInput.value);
        }, 150);
    });

    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            searchInput.value = '';
            renderTree('');
            searchInput.blur();
        }
    });

    // Initial render
    renderTree('');

    // Lightweight selection update — toggle CSS class instead of full re-render
    function _updateSelection(newId) {
        if (newId === selectedNodeId) return;
        // Remove old selection
        if (selectedNodeId) {
            const oldRow = _rowById.get(selectedNodeId);
            if (oldRow) oldRow.classList.remove('selected');
        }
        selectedNodeId = newId;
        // Add new selection
        if (newId) {
            const newRow = _rowById.get(newId);
            if (newRow) {
                newRow.classList.add('selected');
                newRow.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            }
        }
    }

    return {
        selectNode(nodeId) {
            _updateSelection(nodeId);
        },
        clearSelection() {
            _updateSelection(null);
        },
        refresh() {
            renderTree(searchInput.value);
        },
    };
}
