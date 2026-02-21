import * as THREE from 'three';

const DIFF_COLORS = {
    added:    0x00E676,
    removed:  0xFF1744,
    modified: 0xFFD600,
    moved:    0x448AFF,
};

const UNCHANGED_OPACITY = 0.08;
const UNCHANGED_EMISSIVE = 0.02;

let diffData = null;
let diffActive = false;
let summaryEl = null;
let toggleBtn = null;
let _pulseAnimId = null;
let _outlineMeshes = [];
let _addedMeshes = {}; // id -> mesh, for nodes we create that don't exist in the scene

let addedIds = new Set();
let removedIds = new Set();
let modifiedIds = new Set();
let movedIds = new Set();

// Stash original materials so we can restore perfectly
const _origMaterials = new Map();
// Stash original material objects for full swap-back
const _origMaterialObjects = new Map();

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

    // Stash originals and apply diff visuals
    for (const [id, mesh] of Object.entries(nodeMeshes)) {
        if (!_origMaterials.has(id)) {
            _origMaterials.set(id, {
                color: mesh.material.color.getHex(),
                emissive: mesh.material.emissive.getHex(),
                emissiveIntensity: mesh.material.emissiveIntensity,
                opacity: mesh.material.opacity,
                transparent: mesh.material.transparent,
            });
        }

        const diffColor = _getDiffColor(id);
        if (diffColor !== null) {
            // Swap to flat BasicMaterial for pure, unmistakable color
            _origMaterialObjects.set(id, mesh.material);
            mesh.material = new THREE.MeshBasicMaterial({
                color: diffColor,
                transparent: removedIds.has(id),
                opacity: removedIds.has(id) ? 0.65 : 1.0,
            });

            // Scale up changed nodes so they stand out in the graph
            mesh.scale.set(1.6, 2.0, 1.6);

            // Add wireframe outline
            const outline = new THREE.LineSegments(
                new THREE.EdgesGeometry(mesh.geometry),
                new THREE.LineBasicMaterial({ color: 0xffffff })
            );
            outline.position.copy(mesh.position);
            outline.scale.copy(mesh.scale).multiplyScalar(1.02);
            scene.add(outline);
            _outlineMeshes.push(outline);

            // Add floating diamond marker above the node
            const markerGeo = new THREE.OctahedronGeometry(0.8, 0);
            const markerMat = new THREE.MeshBasicMaterial({ color: diffColor });
            const marker = new THREE.Mesh(markerGeo, markerMat);
            const bbox = new THREE.Box3().setFromObject(mesh);
            marker.position.set(mesh.position.x, bbox.max.y + 2.0, mesh.position.z);
            scene.add(marker);
            _outlineMeshes.push(marker);

            // Add vertical line from node to marker
            const lineGeo = new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(mesh.position.x, bbox.max.y, mesh.position.z),
                new THREE.Vector3(mesh.position.x, bbox.max.y + 1.4, mesh.position.z),
            ]);
            const lineMat = new THREE.LineBasicMaterial({ color: diffColor });
            const line = new THREE.Line(lineGeo, lineMat);
            scene.add(line);
            _outlineMeshes.push(line);
        } else {
            // Unchanged: ghost it
            mesh.material.transparent = true;
            mesh.material.opacity = UNCHANGED_OPACITY;
            mesh.material.emissiveIntensity = UNCHANGED_EMISSIVE;
        }
    }

    // Create meshes for added nodes that don't exist in the scene
    const LAYER_SPACING = 12;
    let addedIndex = 0;
    for (const addedNode of diff.added_nodes) {
        if (nodeMeshes[addedNode.id]) continue; // already has a mesh
        const level = addedNode.abstraction_level || 1;
        const y = level * LAYER_SPACING;
        const height = Math.max(1.5, Math.log2(Math.max(1, addedNode.lines_of_code)) * 0.64);
        const size = level >= 2 ? 4 : 2;

        // Place added nodes on the right side of the layer, spaced apart
        const xOffset = 18 + addedIndex * 6;
        const zOffset = -10;

        const geo = new THREE.BoxGeometry(size, height, size);
        const mat = new THREE.MeshBasicMaterial({ color: DIFF_COLORS.added });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.set(xOffset, y + height / 2 + 0.1, zOffset);
        mesh.scale.set(1.6, 2.0, 1.6);
        scene.add(mesh);
        _addedMeshes[addedNode.id] = mesh;
        _outlineMeshes.push(mesh);

        // Outline
        const outline = new THREE.LineSegments(
            new THREE.EdgesGeometry(geo),
            new THREE.LineBasicMaterial({ color: 0xffffff })
        );
        outline.position.copy(mesh.position);
        outline.scale.copy(mesh.scale).multiplyScalar(1.02);
        scene.add(outline);
        _outlineMeshes.push(outline);

        // Diamond marker
        const markerGeo = new THREE.OctahedronGeometry(0.8, 0);
        const markerMat = new THREE.MeshBasicMaterial({ color: DIFF_COLORS.added });
        const marker = new THREE.Mesh(markerGeo, markerMat);
        const bbox = new THREE.Box3().setFromObject(mesh);
        marker.position.set(mesh.position.x, bbox.max.y + 2.0, mesh.position.z);
        scene.add(marker);
        _outlineMeshes.push(marker);

        // Vertical line
        const lineGeo = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(mesh.position.x, bbox.max.y, mesh.position.z),
            new THREE.Vector3(mesh.position.x, bbox.max.y + 1.4, mesh.position.z),
        ]);
        const lineMat = new THREE.LineBasicMaterial({ color: DIFF_COLORS.added });
        const line = new THREE.Line(lineGeo, lineMat);
        scene.add(line);
        _outlineMeshes.push(line);

        addedIndex++;
    }

    _colorDiffEdges(diff, edgeMeshes);
    _showSummary(diff);
    _updateToggleButton(true);
    _startPulse(nodeMeshes);
}

export function deactivateDiffMode(nodeMeshes, edgeMeshes, scene) {
    diffActive = false;
    _stopPulse();

    // Reset any scaled meshes
    for (const [id, mesh] of Object.entries(nodeMeshes)) {
        mesh.scale.setScalar(1.0);
    }

    // Remove outline meshes
    for (const m of _outlineMeshes) {
        if (scene) scene.remove(m);
        m.geometry.dispose();
        m.material.dispose();
    }
    _outlineMeshes = [];

    // Restore original materials
    for (const [id, mesh] of Object.entries(nodeMeshes)) {
        const origMat = _origMaterialObjects.get(id);
        if (origMat) {
            // Dispose the temporary BasicMaterial
            mesh.material.dispose();
            mesh.material = origMat;
        } else {
            const orig = _origMaterials.get(id);
            if (orig) {
                mesh.material.color.setHex(orig.color);
                mesh.material.emissive.setHex(orig.emissive);
                mesh.material.emissiveIntensity = orig.emissiveIntensity;
                mesh.material.opacity = orig.opacity;
                mesh.material.transparent = orig.transparent;
            }
        }
    }
    _origMaterials.clear();
    _origMaterialObjects.clear();

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

    addedIds.clear();
    removedIds.clear();
    modifiedIds.clear();
    movedIds.clear();

    _addedMeshes = {};

    _hideSummary();
    _updateToggleButton(false);
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

function _getDiffColor(id) {
    if (addedIds.has(id)) return DIFF_COLORS.added;
    if (removedIds.has(id)) return DIFF_COLORS.removed;
    if (modifiedIds.has(id)) return DIFF_COLORS.modified;
    if (movedIds.has(id)) return DIFF_COLORS.moved;
    return null;
}

function _startPulse(nodeMeshes) {
    _stopPulse();
    // Collect diamond markers (OctahedronGeometry meshes) for spinning
    const markers = _outlineMeshes.filter(m => m.geometry && m.geometry.type === 'OctahedronGeometry');
    if (markers.length === 0) return;

    function pulse() {
        const t = performance.now() * 0.001;
        for (const marker of markers) {
            marker.rotation.y = t * 2;
            marker.position.y += Math.sin(t * 3) * 0.003;
        }
        _pulseAnimId = requestAnimationFrame(pulse);
    }
    _pulseAnimId = requestAnimationFrame(pulse);
}

function _stopPulse() {
    if (_pulseAnimId !== null) {
        cancelAnimationFrame(_pulseAnimId);
        _pulseAnimId = null;
    }
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
                color = new THREE.Color(data.baseColor).multiplyScalar(0.15);
            }
            for (let i = range.start; i < range.end; i++) {
                colors.setXYZ(i, color.r, color.g, color.b);
            }
        }
        colors.needsUpdate = true;
        data.line.material.opacity = 0.5;
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

    const stats = [
        { count: s.added_nodes, label: 'added', color: '#00E676', symbol: '\u25CF' },
        { count: s.removed_nodes, label: 'removed', color: '#FF1744', symbol: '\u25CF' },
        { count: s.modified_nodes, label: 'modified', color: '#FFD600', symbol: '\u25CF' },
        { count: s.moved_nodes, label: 'moved', color: '#448AFF', symbol: '\u25CF' },
    ];
    for (const stat of stats) {
        if (!stat.count) continue;
        const span = document.createElement('span');
        span.style.color = stat.color;
        span.style.marginRight = '10px';
        span.style.fontWeight = 'bold';
        span.textContent = `${stat.symbol} ${stat.count} ${stat.label}`;
        summaryEl.appendChild(span);
    }

    summaryEl.style.display = 'block';
}

function _hideSummary() {
    if (summaryEl) summaryEl.style.display = 'none';
}

function _updateToggleButton(active) {
    if (!toggleBtn) toggleBtn = document.getElementById('btn-toggle-diff');
    if (!toggleBtn) return;
    toggleBtn.style.display = 'inline-block';
    if (active) {
        toggleBtn.textContent = 'Hide Diff';
        toggleBtn.style.background = 'rgba(140, 96, 243, 0.15)';
        toggleBtn.style.borderColor = '#8c60f3';
    } else {
        toggleBtn.textContent = 'Show Diff';
        toggleBtn.style.background = '';
        toggleBtn.style.borderColor = '';
    }
}

function _shortName(id) {
    const parts = id.split('/');
    return parts[parts.length - 1] || id;
}
