import * as THREE from 'three';

const DIFF_COLORS = {
    added:    0x4CAF50,
    removed:  0xF44336,
    modified: 0xFFC107,
    moved:    0x2196F3,
};

const UNCHANGED_OPACITY = 0.3;

let diffData = null;
let diffActive = false;
let summaryEl = null;
let clearBtn = null;

// Sets of node IDs by diff state
let addedIds = new Set();
let removedIds = new Set();
let modifiedIds = new Set();
let movedIds = new Set();

export function getDiffState() {
    return { diffActive, addedIds, removedIds, modifiedIds, movedIds, diffData };
}

export async function loadDiff(basePath = '.') {
    try {
        const res = await fetch(`${basePath}/.callgraph/diff.json?t=${Date.now()}`);
        if (!res.ok) return null;
        return await res.json();
    } catch {
        return null;
    }
}

export function activateDiffMode(diff, nodeMeshes, edgeMeshes, scene) {
    diffData = diff;
    diffActive = true;

    addedIds = new Set(diff.added_nodes.map(n => n.id));
    removedIds = new Set(diff.removed_nodes.map(n => n.id));
    modifiedIds = new Set(diff.modified_nodes.map(n => n.id));
    movedIds = new Set(diff.moved_nodes.map(n => n.id));

    // Apply node colors
    for (const [id, mesh] of Object.entries(nodeMeshes)) {
        if (addedIds.has(id)) {
            _applyGlow(mesh, DIFF_COLORS.added, 1.0);
        } else if (removedIds.has(id)) {
            _applyGlow(mesh, DIFF_COLORS.removed, 0.5);
        } else if (modifiedIds.has(id)) {
            _applyGlow(mesh, DIFF_COLORS.modified, 1.0);
        } else if (movedIds.has(id)) {
            _applyGlow(mesh, DIFF_COLORS.moved, 1.0);
        } else {
            // Dim unchanged
            mesh.material.transparent = true;
            mesh.material.opacity = UNCHANGED_OPACITY;
            mesh.material.emissiveIntensity = 0.05;
        }
    }

    // Apply edge coloring
    _colorDiffEdges(diff, edgeMeshes);

    // Show summary panel
    _showSummary(diff);
    _showClearButton();
}

export function deactivateDiffMode(nodeMeshes, edgeMeshes) {
    diffData = null;
    diffActive = false;
    addedIds.clear();
    removedIds.clear();
    modifiedIds.clear();
    movedIds.clear();

    // Restore node materials
    for (const [id, mesh] of Object.entries(nodeMeshes)) {
        mesh.material.transparent = false;
        mesh.material.opacity = 1.0;
        mesh.material.emissiveIntensity = 0.15;
        mesh.material.emissive.setHex(0x000000);
    }

    // Restore edge colors
    for (const [type, data] of Object.entries(edgeMeshes)) {
        if (!data.line) continue;
        const colors = data.line.geometry.getAttribute('color');
        if (!colors) continue;
        const base = new THREE.Color(data.baseColor);
        for (let i = 0; i < colors.count; i++) {
            colors.setXYZ(i, base.r, base.g, base.b);
        }
        colors.needsUpdate = true;
        data.line.material.opacity = data.baseOpacity;
    }

    _hideSummary();
    _hideClearButton();
}

export function getDiffHoverInfo(nodeId, diff) {
    if (!diff) return null;
    const lines = [];

    for (const e of diff.added_edges) {
        if (e.from === nodeId) lines.push(`+ dependency: \u2192 ${_shortName(e.to)}`);
        if (e.to === nodeId) lines.push(`+ depended on by: ${_shortName(e.from)}`);
    }
    for (const e of diff.removed_edges) {
        if (e.from === nodeId) lines.push(`- dependency: \u2192 ${_shortName(e.to)}`);
        if (e.to === nodeId) lines.push(`- depended on by: ${_shortName(e.from)}`);
    }

    const mod = diff.modified_nodes.find(n => n.id === nodeId);
    if (mod) {
        for (const [field, [oldVal, newVal]] of Object.entries(mod.changes)) {
            lines.push(`${field}: ${oldVal} \u2192 ${newVal}`);
        }
    }

    return lines.length > 0 ? lines : null;
}

function _applyGlow(mesh, color, opacity) {
    mesh.material.emissive.setHex(color);
    mesh.material.emissiveIntensity = 0.6;
    mesh.material.opacity = opacity;
}

function _colorDiffEdges(diff, edgeMeshes) {
    const addedSet = new Set(diff.added_edges.map(e => `${e.from}|${e.to}`));
    const removedSet = new Set(diff.removed_edges.map(e => `${e.from}|${e.to}`));

    for (const [type, data] of Object.entries(edgeMeshes)) {
        if (!data.line || !data.edgeRanges) continue;
        const colors = data.line.geometry.getAttribute('color');
        if (!colors) continue;

        for (const range of data.edgeRanges) {
            const key = `${range.from}|${range.to}`;
            let color;
            if (addedSet.has(key)) {
                color = new THREE.Color(DIFF_COLORS.added);
            } else if (removedSet.has(key)) {
                color = new THREE.Color(DIFF_COLORS.removed);
            } else {
                // Dim unchanged edges
                color = new THREE.Color(data.baseColor).multiplyScalar(0.3);
            }
            for (let i = range.start; i < range.end; i++) {
                colors.setXYZ(i, color.r, color.g, color.b);
            }
        }
        colors.needsUpdate = true;
        data.line.material.opacity = 0.7;
    }
}

function _showSummary(diff) {
    if (!summaryEl) {
        summaryEl = document.createElement('div');
        summaryEl.id = 'diff-summary';
        document.body.appendChild(summaryEl);
    }
    summaryEl.textContent = '';

    const meta = diff.meta || {};
    const s = diff.summary;

    // Title
    let title;
    if (meta.source === 'commits') {
        title = `Diff: ${meta.ref_a}..${meta.ref_b}`;
    } else if (meta.source === 'plan') {
        title = `Plan: ${meta.plan_name}`;
    } else {
        title = 'Diff';
    }
    const titleEl = document.createElement('strong');
    titleEl.textContent = title;
    summaryEl.appendChild(titleEl);
    summaryEl.appendChild(document.createElement('br'));

    // Stats
    const stats = [
        { count: s.added_nodes, label: 'added', color: '#4CAF50' },
        { count: s.removed_nodes, label: 'removed', color: '#F44336' },
        { count: s.modified_nodes, label: 'modified', color: '#FFC107' },
        { count: s.moved_nodes, label: 'moved', color: '#2196F3' },
    ];
    for (const stat of stats) {
        if (!stat.count) continue;
        const span = document.createElement('span');
        span.style.color = stat.color;
        span.style.marginRight = '8px';
        const prefix = stat.label === 'removed' ? '-' : stat.label === 'modified' ? '~' : stat.label === 'moved' ? '>' : '+';
        span.textContent = `${prefix}${stat.count} ${stat.label}`;
        summaryEl.appendChild(span);
    }

    summaryEl.style.display = 'block';
}

function _hideSummary() {
    if (summaryEl) summaryEl.style.display = 'none';
}

function _showClearButton() {
    if (!clearBtn) clearBtn = document.getElementById('btn-clear-diff');
    if (clearBtn) clearBtn.style.display = 'inline-block';
}

function _hideClearButton() {
    if (!clearBtn) clearBtn = document.getElementById('btn-clear-diff');
    if (clearBtn) clearBtn.style.display = 'none';
}

function _shortName(id) {
    const parts = id.split('/');
    return parts[parts.length - 1] || id;
}
