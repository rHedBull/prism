/**
 * 2D semantic zoom mode.
 * Orthographic top-down camera with grid-packed card layout and edge rendering.
 */
import * as THREE from 'three';
import * as TWEEN from '@tweenjs/tween.js';
import { buildNestedTreemap } from './layout-treemap.js';
import { computeColor, computeMetricRange } from './metrics.js';
import { requestRender, getCanvasWidth } from './scene.js';

const LAYER_COLORS = {
    0: 0x4A90D9, 1: 0x8c60f3, 2: 0x2ECC71, 3: 0xE74C3C,
};

const EDGE_COLORS_2D = {
    imports: 0x8c60f3,
    calls: 0x353148,
    inherits_from: 0x6a3fd4,
    depends_on: 0x8e8a9c,
};

// Zoom thresholds: frustum half-width at which each layer becomes visible
const ZOOM_THRESHOLDS = {
    3: Infinity,  // C1 always visible
    2: 60,        // C2 appears when frustum < 60
    1: 30,        // C3 appears when frustum < 30
    0: 15,        // C4 appears when frustum < 15
};

const FADE_RANGE = 5;
const CORNER_RADIUS = 0.6;

let _camera2d = null;
let _meshGroup = null;
let _treemapLayout = null;
let _nodeMeshes2d = {};
let _containerMeshes = {};
let _labelSprites = {};
let _edgeLines2d = [];
let _layerGroups = null;
let _nodeDataMap2d = new Map();
let _totalW = 80;
let _totalD = 80;
let _isPanning = false;
let _panStart = { x: 0, y: 0 };
let _cameraStart = { x: 0, z: 0 };

/**
 * Create a rounded rectangle THREE.Shape.
 */
function createRoundedRectShape(w, d, radius) {
    const r = Math.min(radius, w / 2, d / 2);
    const shape = new THREE.Shape();
    shape.moveTo(r, 0);
    shape.lineTo(w - r, 0);
    shape.quadraticCurveTo(w, 0, w, r);
    shape.lineTo(w, d - r);
    shape.quadraticCurveTo(w, d, w - r, d);
    shape.lineTo(r, d);
    shape.quadraticCurveTo(0, d, 0, d - r);
    shape.lineTo(0, r);
    shape.quadraticCurveTo(0, 0, r, 0);
    return shape;
}

export function create2DCamera() {
    const aspect = getCanvasWidth() / window.innerHeight;
    const halfH = _totalD * 0.6;
    const halfW = halfH * aspect;
    _camera2d = new THREE.OrthographicCamera(
        -halfW, halfW,
        halfH, -halfH,
        0.1, 100
    );
    _camera2d.position.set(_totalW / 2, 50, _totalD / 2);
    _camera2d.lookAt(_totalW / 2, 0, _totalD / 2);
    _camera2d.up.set(0, 0, -1);
    return _camera2d;
}

export function get2DCamera() { return _camera2d; }
export function get2DNodeMeshes() { return _nodeMeshes2d; }
export function get2DNodeDataMap() { return _nodeDataMap2d; }

/**
 * Build all 2D meshes from layerGroups data, plus edge lines.
 */
export function build2DScene(layerGroups, scene, edges) {
    _layerGroups = layerGroups;

    // Clean up previous 2D scene
    if (_meshGroup) {
        scene.remove(_meshGroup);
        _meshGroup.traverse(child => {
            if (child.geometry) child.geometry.dispose();
            if (child.material) {
                if (child.material.map) child.material.map.dispose();
                child.material.dispose();
            }
        });
    }

    _meshGroup = new THREE.Group();
    _nodeMeshes2d = {};
    _containerMeshes = {};
    _labelSprites = {};
    _edgeLines2d = [];
    _nodeDataMap2d = new Map();

    const allNodes = Object.values(layerGroups).flat();
    const totalNodes = allNodes.length;
    const area = Math.max(60, Math.sqrt(totalNodes) * 8) ** 2;
    const aspect = getCanvasWidth() / window.innerHeight;
    _totalW = Math.sqrt(area * aspect);
    _totalD = _totalW / aspect;

    _treemapLayout = buildNestedTreemap(layerGroups, _totalW, _totalD);

    const metricRange = computeMetricRange(allNodes);

    for (const [nodeId, rect] of _treemapLayout) {
        const node = allNodes.find(n => n.id === nodeId);
        if (!node) continue;

        const level = rect.level;
        const color = computeColor(node, metricRange);

        // Rounded-rect shape geometry
        const shape = createRoundedRectShape(rect.w, rect.d, CORNER_RADIUS);
        const geo = new THREE.ShapeGeometry(shape);
        const mat = new THREE.MeshBasicMaterial({
            color,
            transparent: true,
            opacity: 1.0,
            side: THREE.DoubleSide,
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.rotation.x = -Math.PI / 2;
        // ShapeGeometry is drawn from (0,0) so position at rect corner
        mesh.position.set(rect.x, level * 0.01, rect.z + rect.d);
        mesh.userData = { type: 'node', nodeData: node, _origColor: color, _rect: rect };
        _meshGroup.add(mesh);
        _nodeMeshes2d[nodeId] = mesh;
        _nodeDataMap2d.set(mesh, node);

        // Outline from shape edges
        const points = shape.getPoints(16);
        const outlineGeo = new THREE.BufferGeometry().setFromPoints(
            points.map(p => new THREE.Vector3(p.x, 0, -p.y))
        );
        // Close the loop
        const first = points[0];
        const posArr = outlineGeo.attributes.position.array;
        const closeGeo = new THREE.BufferGeometry().setFromPoints([
            ...points.map(p => new THREE.Vector3(p.x, 0, -p.y)),
            new THREE.Vector3(first.x, 0, -first.y),
        ]);
        const edgesMat = new THREE.LineBasicMaterial({
            color: LAYER_COLORS[level] || 0x666666,
            transparent: true,
            opacity: 0.6,
        });
        const outline = new THREE.Line(closeGeo, edgesMat);
        outline.position.set(rect.x, level * 0.01 + 0.005, rect.z + rect.d);
        _meshGroup.add(outline);
        _containerMeshes[nodeId] = outline;
        outlineGeo.dispose();

        // Label sprite
        const isLeafLevel = !layerGroups[level - 1] || (layerGroups[level - 1] || []).every(n => n._layerParent !== nodeId);
        const label = _createLabel(node.name, LAYER_COLORS[level] || 0x666666);
        if (isLeafLevel) {
            // Center label for leaf nodes
            label.position.set(rect.x + rect.w / 2, level * 0.01 + 0.02, rect.z + rect.d / 2);
        } else {
            // Top label for containers
            label.position.set(rect.x + rect.w / 2, level * 0.01 + 0.02, rect.z + 0.8);
        }
        const labelScale = Math.min(rect.w * 0.8, 8);
        label.scale.set(labelScale, labelScale * 0.15, 1);
        _meshGroup.add(label);
        _labelSprites[nodeId] = label;
    }

    // --- Edge rendering ---
    if (edges) {
        // Build parent map for resolving edges to visible 2D meshes
        const parentMap = {};
        for (const node of allNodes) {
            if (node.parent) parentMap[node.id] = node.parent;
        }

        function resolveMesh2D(nodeId) {
            let id = nodeId;
            const visited = new Set();
            while (id && !visited.has(id)) {
                if (_nodeMeshes2d[id]) return { mesh: _nodeMeshes2d[id], id };
                visited.add(id);
                id = parentMap[id];
            }
            return null;
        }

        for (const edge of edges) {
            if (edge.type === 'contains') continue;

            const fromRes = resolveMesh2D(edge.from);
            const toRes = resolveMesh2D(edge.to);
            if (!fromRes || !toRes) continue;
            if (fromRes.id === toRes.id) continue;

            const fromRect = _treemapLayout.get(fromRes.id);
            const toRect = _treemapLayout.get(toRes.id);
            if (!fromRect || !toRect) continue;

            // Center points of source and target cards
            const sx = fromRect.x + fromRect.w / 2;
            const sz = fromRect.z + fromRect.d / 2;
            const tx = toRect.x + toRect.w / 2;
            const tz = toRect.z + toRect.d / 2;

            const start = new THREE.Vector3(sx, 0.03, sz);
            const end = new THREE.Vector3(tx, 0.03, tz);

            // Quadratic bezier with perpendicular offset
            const mid = start.clone().add(end).multiplyScalar(0.5);
            const dx = tx - sx;
            const dz = tz - sz;
            const len = Math.sqrt(dx * dx + dz * dz);
            if (len < 0.1) continue;

            // Perpendicular offset to avoid overlapping straight lines
            const perpX = -dz / len;
            const perpZ = dx / len;
            const offset = Math.min(len * 0.15, 3);
            mid.x += perpX * offset;
            mid.z += perpZ * offset;

            const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
            const points = curve.getPoints(20);
            const geometry = new THREE.BufferGeometry().setFromPoints(points);

            const color = EDGE_COLORS_2D[edge.type] || 0x444444;
            const material = new THREE.LineBasicMaterial({
                color,
                transparent: true,
                opacity: 0.3,
            });
            const line = new THREE.Line(geometry, material);
            line.userData = {
                type: 'edge2d',
                edgeData: edge,
                fromId: fromRes.id,
                toId: toRes.id,
            };
            _meshGroup.add(line);
            _edgeLines2d.push(line);
        }
    }

    scene.add(_meshGroup);

    // Reset camera to fit
    if (_camera2d) {
        const camAspect = getCanvasWidth() / window.innerHeight;
        const halfH = _totalD * 0.6;
        const halfW = halfH * camAspect;
        _camera2d.left = -halfW;
        _camera2d.right = halfW;
        _camera2d.top = halfH;
        _camera2d.bottom = -halfH;
        _camera2d.position.set(_totalW / 2, 50, _totalD / 2);
        _camera2d.lookAt(_totalW / 2, 0, _totalD / 2);
        _camera2d.updateProjectionMatrix();
    }

    updateSemanticZoom();

    return { meshGroup: _meshGroup, nodeMeshes2d: _nodeMeshes2d, nodeDataMap2d: _nodeDataMap2d };
}

/**
 * Update visibility and opacity of nodes based on current zoom level.
 */
export function updateSemanticZoom() {
    if (!_camera2d || !_treemapLayout) return;

    const frustumHalf = (_camera2d.top - _camera2d.bottom) / 2;

    for (const [nodeId, rect] of _treemapLayout) {
        const mesh = _nodeMeshes2d[nodeId];
        const outline = _containerMeshes[nodeId];
        const label = _labelSprites[nodeId];
        if (!mesh) continue;

        const level = rect.level;
        const threshold = ZOOM_THRESHOLDS[level];
        const visible = frustumHalf <= threshold;

        const deeperLevel = level - 1;
        const deeperThreshold = ZOOM_THRESHOLDS[deeperLevel];
        const deeperVisible = deeperLevel >= 0 && frustumHalf <= deeperThreshold;

        if (!visible) {
            mesh.visible = false;
            if (outline) outline.visible = false;
            if (label) label.visible = false;
            continue;
        }

        mesh.visible = true;

        if (deeperVisible) {
            // Container mode — show as outline only
            mesh.material.opacity = 0.08;
            if (outline) { outline.visible = true; outline.material.opacity = 0.5; }
            if (label) { label.visible = true; label.material.opacity = 0.7; }
        } else {
            // Leaf at current zoom — show filled
            const fadeStart = threshold;
            const fadeEnd = threshold - FADE_RANGE;
            let opacity = 1.0;
            if (frustumHalf > fadeEnd && frustumHalf <= fadeStart) {
                opacity = 1.0 - (frustumHalf - fadeEnd) / FADE_RANGE;
            }
            mesh.material.opacity = Math.max(0.3, opacity);
            if (outline) { outline.visible = true; outline.material.opacity = 0.8; }
            if (label) { label.visible = true; label.material.opacity = opacity; }
        }
    }

    // Edge visibility: show only when both endpoints are visible leaf nodes
    for (const line of _edgeLines2d) {
        const fromMesh = _nodeMeshes2d[line.userData.fromId];
        const toMesh = _nodeMeshes2d[line.userData.toId];
        if (!fromMesh || !toMesh) {
            line.visible = false;
            continue;
        }

        const fromVisible = fromMesh.visible && fromMesh.material.opacity > 0.1;
        const toVisible = toMesh.visible && toMesh.material.opacity > 0.1;

        if (fromVisible && toVisible) {
            line.visible = true;
            line.material.opacity = Math.min(fromMesh.material.opacity, toMesh.material.opacity) * 0.4;
        } else {
            line.visible = false;
        }
    }
}

/**
 * Handle scroll zoom for 2D mode.
 */
export function setup2DControls(renderer) {
    const canvas = renderer.domElement;

    canvas.addEventListener('wheel', (e) => {
        if (!_camera2d || window._viewMode !== '2d') return;
        e.preventDefault();

        const zoomFactor = e.deltaY > 0 ? 1.1 : 0.9;
        const aspect = getCanvasWidth() / window.innerHeight;

        const rect = canvas.getBoundingClientRect();
        const mx = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        const my = -((e.clientY - rect.top) / rect.height) * 2 + 1;

        // halfH is the canonical frustum half-size (aspect-independent)
        const halfH = (_camera2d.top - _camera2d.bottom) / 2;
        const halfW = halfH * aspect;
        const worldX = _camera2d.position.x + mx * halfW;
        const worldZ = _camera2d.position.z - my * halfH;

        const newHalfH = halfH * zoomFactor;
        const minZoom = 3;
        const maxZoom = Math.max(_totalW, _totalD) * 1.2;
        const clampedH = Math.max(minZoom, Math.min(maxZoom, newHalfH));
        const clampedW = clampedH * aspect;

        _camera2d.left = -clampedW;
        _camera2d.right = clampedW;
        _camera2d.top = clampedH;
        _camera2d.bottom = -clampedH;

        // Adjust camera position to zoom toward mouse
        _camera2d.position.x = worldX - mx * clampedW;
        _camera2d.position.z = worldZ + my * clampedH;

        _camera2d.updateProjectionMatrix();
        updateSemanticZoom();
        requestRender();
    }, { passive: false });

    // Pan with right-click drag or middle-click drag
    canvas.addEventListener('mousedown', (e) => {
        if (!_camera2d || window._viewMode !== '2d') return;
        if (e.button === 2 || e.button === 1) {
            _isPanning = true;
            _panStart = { x: e.clientX, y: e.clientY };
            _cameraStart = { x: _camera2d.position.x, z: _camera2d.position.z };
            e.preventDefault();
        }
    });

    window.addEventListener('mousemove', (e) => {
        if (!_isPanning || !_camera2d || window._viewMode !== '2d') return;
        const dx = e.clientX - _panStart.x;
        const dy = e.clientY - _panStart.y;

        const frustumW = _camera2d.right - _camera2d.left;
        const frustumH = _camera2d.top - _camera2d.bottom;
        const canvasW = getCanvasWidth();
        const canvasH = window.innerHeight;

        _camera2d.position.x = _cameraStart.x - (dx / canvasW) * frustumW;
        _camera2d.position.z = _cameraStart.z - (dy / canvasH) * frustumH;
        _camera2d.updateProjectionMatrix();
        requestRender();
    });

    window.addEventListener('mouseup', (e) => {
        if (e.button === 2 || e.button === 1) {
            _isPanning = false;
        }
    });

    canvas.addEventListener('contextmenu', (e) => {
        if (window._viewMode === '2d') e.preventDefault();
    });
}

/**
 * Animate zoom into a specific node.
 */
export function zoomToNode(nodeId) {
    if (!_camera2d || !_treemapLayout) return;
    const rect = _treemapLayout.get(nodeId);
    if (!rect) return;

    const aspect = getCanvasWidth() / window.innerHeight;
    const targetHalf = Math.max(rect.w, rect.d) * 0.8;
    const targetX = rect.x + rect.w / 2;
    const targetZ = rect.z + rect.d / 2;

    const startTop = _camera2d.top;
    const startX = _camera2d.position.x;
    const startZ = _camera2d.position.z;

    new TWEEN.Tween({ t: 0 })
        .to({ t: 1 }, 600)
        .easing(TWEEN.Easing.Cubic.InOut)
        .onUpdate(({ t }) => {
            const half = startTop + (targetHalf - startTop) * t;
            _camera2d.left = -half * aspect;
            _camera2d.right = half * aspect;
            _camera2d.top = half;
            _camera2d.bottom = -half;
            _camera2d.position.x = startX + (targetX - startX) * t;
            _camera2d.position.z = startZ + (targetZ - startZ) * t;
            _camera2d.updateProjectionMatrix();
            updateSemanticZoom();
            requestRender();
        })
        .start();
    requestRender();
}

/**
 * Clean up 2D scene meshes.
 */
export function destroy2DScene(scene) {
    if (_meshGroup) {
        scene.remove(_meshGroup);
        _meshGroup.traverse(child => {
            if (child.geometry) child.geometry.dispose();
            if (child.material) {
                if (child.material.map) child.material.map.dispose();
                child.material.dispose();
            }
        });
        _meshGroup = null;
    }
    _nodeMeshes2d = {};
    _containerMeshes = {};
    _labelSprites = {};
    _edgeLines2d = [];
    _nodeDataMap2d = new Map();
    _treemapLayout = null;
}

export function resize2DCamera() {
    if (!_camera2d) return;
    const aspect = getCanvasWidth() / window.innerHeight;
    const halfH = (_camera2d.top - _camera2d.bottom) / 2;
    _camera2d.left = -halfH * aspect;
    _camera2d.right = halfH * aspect;
    _camera2d.updateProjectionMatrix();
}

function _createLabel(text, color) {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.font = 'bold 28px monospace';
    ctx.fillStyle = `#${new THREE.Color(color).getHexString()}`;
    ctx.fillText(text, 10, 44);

    const texture = new THREE.CanvasTexture(canvas);
    texture.premultiplyAlpha = true;
    const mat = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false });
    return new THREE.Sprite(mat);
}
