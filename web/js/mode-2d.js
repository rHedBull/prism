/**
 * 2D semantic zoom mode.
 * Orthographic top-down camera with nested treemap layout.
 */
import * as THREE from 'three';
import * as TWEEN from '@tweenjs/tween.js';
import { buildNestedTreemap } from './layout-treemap.js';
import { computeColor, computeMetricRange } from './metrics.js';
import { requestRender, getCanvasWidth } from './scene.js';

const LAYER_COLORS = {
    0: 0x4A90D9, 1: 0x8c60f3, 2: 0x2ECC71, 3: 0xE74C3C,
};

// Zoom thresholds: frustum half-width at which each layer becomes visible
const ZOOM_THRESHOLDS = {
    3: Infinity,  // C1 always visible
    2: 60,        // C2 appears when frustum < 60
    1: 30,        // C3 appears when frustum < 30
    0: 15,        // C4 appears when frustum < 15
};

const FADE_RANGE = 5;

let _camera2d = null;
let _meshGroup = null;
let _treemapLayout = null;
let _nodeMeshes2d = {};
let _containerMeshes = {};
let _labelSprites = {};
let _layerGroups = null;
let _nodeDataMap2d = new Map();
let _totalSize = 80;
let _isPanning = false;
let _panStart = { x: 0, y: 0 };
let _cameraStart = { x: 0, z: 0 };

export function create2DCamera() {
    const aspect = getCanvasWidth() / window.innerHeight;
    const frustumHalf = _totalSize * 0.6;
    _camera2d = new THREE.OrthographicCamera(
        -frustumHalf * aspect, frustumHalf * aspect,
        frustumHalf, -frustumHalf,
        0.1, 100
    );
    _camera2d.position.set(_totalSize / 2, 50, _totalSize / 2);
    _camera2d.lookAt(_totalSize / 2, 0, _totalSize / 2);
    _camera2d.up.set(0, 0, -1);
    return _camera2d;
}

export function get2DCamera() { return _camera2d; }
export function get2DNodeMeshes() { return _nodeMeshes2d; }
export function get2DNodeDataMap() { return _nodeDataMap2d; }

/**
 * Build all 2D meshes from layerGroups data.
 */
export function build2DScene(layerGroups, scene) {
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
    _nodeDataMap2d = new Map();

    const allNodes = Object.values(layerGroups).flat();
    const totalNodes = allNodes.length;
    _totalSize = Math.max(60, Math.sqrt(totalNodes) * 8);

    _treemapLayout = buildNestedTreemap(layerGroups, _totalSize, _totalSize);

    const metricRange = computeMetricRange(allNodes);

    for (const [nodeId, rect] of _treemapLayout) {
        const node = allNodes.find(n => n.id === nodeId);
        if (!node) continue;

        const level = rect.level;

        const color = computeColor(node, metricRange);
        const geo = new THREE.PlaneGeometry(rect.w, rect.d);
        const mat = new THREE.MeshBasicMaterial({
            color,
            transparent: true,
            opacity: 1.0,
            side: THREE.DoubleSide,
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.rotation.x = -Math.PI / 2;
        mesh.position.set(rect.x + rect.w / 2, level * 0.01, rect.z + rect.d / 2);
        mesh.userData = { type: 'node', nodeData: node, _origColor: color, _rect: rect };
        _meshGroup.add(mesh);
        _nodeMeshes2d[nodeId] = mesh;
        _nodeDataMap2d.set(mesh, node);

        // Container outline
        const edgesGeo = new THREE.EdgesGeometry(geo);
        const edgesMat = new THREE.LineBasicMaterial({
            color: LAYER_COLORS[level] || 0x666666,
            transparent: true,
            opacity: 0.6,
        });
        const outline = new THREE.LineSegments(edgesGeo, edgesMat);
        outline.rotation.x = -Math.PI / 2;
        outline.position.set(rect.x + rect.w / 2, level * 0.01 + 0.005, rect.z + rect.d / 2);
        _meshGroup.add(outline);
        _containerMeshes[nodeId] = outline;

        // Label sprite
        const label = _createLabel(node.name, LAYER_COLORS[level] || 0x666666);
        label.position.set(rect.x + rect.w / 2, level * 0.01 + 0.02, rect.z + 0.8);
        const labelScale = Math.min(rect.w * 0.8, 8);
        label.scale.set(labelScale, labelScale * 0.15, 1);
        _meshGroup.add(label);
        _labelSprites[nodeId] = label;
    }

    scene.add(_meshGroup);

    // Reset camera to fit
    if (_camera2d) {
        const aspect = getCanvasWidth() / window.innerHeight;
        const frustumHalf = _totalSize * 0.6;
        _camera2d.left = -frustumHalf * aspect;
        _camera2d.right = frustumHalf * aspect;
        _camera2d.top = frustumHalf;
        _camera2d.bottom = -frustumHalf;
        _camera2d.position.set(_totalSize / 2, 50, _totalSize / 2);
        _camera2d.lookAt(_totalSize / 2, 0, _totalSize / 2);
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

    const frustumHalf = (_camera2d.right - _camera2d.left) / 2;

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

        const halfW = (_camera2d.right - _camera2d.left) / 2;
        const halfH = (_camera2d.top - _camera2d.bottom) / 2;
        const worldX = _camera2d.position.x + mx * halfW;
        const worldZ = _camera2d.position.z - my * halfH;

        const newHalfW = halfW * zoomFactor;
        const minZoom = 3;
        const maxZoom = _totalSize * 1.2;
        const clampedHalf = Math.max(minZoom, Math.min(maxZoom, newHalfW));

        _camera2d.left = -clampedHalf * aspect;
        _camera2d.right = clampedHalf * aspect;
        _camera2d.top = clampedHalf;
        _camera2d.bottom = -clampedHalf;

        // Adjust camera position to zoom toward mouse
        _camera2d.position.x = worldX - mx * clampedHalf;
        _camera2d.position.z = worldZ + my * clampedHalf;

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
        _camera2d.position.z = _cameraStart.z + (dy / canvasH) * frustumH;
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
